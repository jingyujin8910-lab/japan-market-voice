from datetime import date
from typing import Any, Dict, List, Mapping, Optional

from japan_voice.collectors.youtube import YouTubeCollector
from japan_voice.config.settings import Settings
from japan_voice.domain.enums import CollectorStatus, ContentGroup, Source
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError


def search_payload(*video_ids: str) -> Dict[str, Any]:
    return {"items": [{"id": {"videoId": video_id}} for video_id in video_ids]}


def video_item(
    video_id: str,
    title: Optional[str] = None,
    description: str = "日本市場向けの車両を紹介",
) -> Dict[str, Any]:
    return {
        "id": video_id,
        "statistics": {"commentCount": "66"},
        "snippet": {
            "title": title or f"Kia PV5 日本発売 {video_id}",
            "description": description,
            "channelTitle": "日本カー情報",
            "channelId": "channel-1",
            "publishedAt": "2026-08-10T03:00:00Z",
        },
    }


def comment_item(comment_id: str, text: str = "日本でも欲しい") -> Dict[str, Any]:
    return {
        "id": f"thread-{comment_id}",
        "snippet": {
            "topLevelComment": {
                "id": comment_id,
                "snippet": {
                    "textDisplay": text,
                    "publishedAt": "2026-08-11T04:00:00Z",
                    "likeCount": 7,
                    "authorDisplayName": "公開ユーザー",
                },
            }
        },
    }


class FakeHttp:
    def __init__(
        self,
        *,
        search: Optional[List[Any]] = None,
        videos: Any = None,
        comments: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.search = list(search or [])
        self.videos = videos if videos is not None else {"items": []}
        self.comments = dict(comments or {})
        self.calls: List[tuple] = []

    def get_json(self, url: str, *, params: Mapping[str, Any], headers: Any = None) -> Dict[str, Any]:
        self.calls.append((url, dict(params)))
        if url.endswith("/search"):
            value = self.search.pop(0)
        elif url.endswith("/videos"):
            value = self.videos
        elif url.endswith("/commentThreads"):
            value = self.comments[params["videoId"]]
            if isinstance(value, list):
                value = value.pop(0)
        else:
            raise AssertionError(f"unexpected URL: {url}")
        if isinstance(value, Exception):
            raise value
        return value


def make_request(max_results: int = 2) -> SearchRequest:
    return SearchRequest(
        keyword="PV5",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 15),
        selected_sources=[Source.YOUTUBE],
        max_results=max_results,
    )


def collector(http: FakeHttp, *, max_videos: int = 2) -> YouTubeCollector:
    return YouTubeCollector(
        http=http,  # type: ignore[arg-type]
        settings=Settings(youtube_max_videos=max_videos, youtube_comments_per_video=10),
        api_key="test-key-never-logged",
    )


def test_search_success_deduplicates_video_ids_and_fetches_metadata() -> None:
    http = FakeHttp(
        search=[search_payload("v1", "v1", "v2")],
        videos={"items": [video_item("v1"), video_item("v2")]},
        comments={"v1": {"items": []}, "v2": {"items": []}},
    )
    result = collector(http).collect(make_request(), ["PV5 日本"])
    assert result.status is CollectorStatus.SUCCESS
    assert result.metadata["unique_videos"] == 2
    metadata_call = next(params for url, params in http.calls if url.endswith("/videos"))
    assert metadata_call["id"] == "v1,v2"
    assert len([record for record in result.records if record.content_group is ContentGroup.MARKET_CONTENT]) == 2


def test_long_range_search_uses_bounded_month_windows_across_full_period() -> None:
    ids = [f"v{i}" for i in range(1, 9)]
    videos = []
    for month, video_id in enumerate(ids, start=1):
        item = video_item(video_id)
        item["snippet"]["publishedAt"] = f"2026-{month:02d}-10T03:00:00Z"
        videos.append(item)
    http = FakeHttp(
        search=[search_payload(video_id) for video_id in ids],
        videos={"items": videos},
        comments={video_id: {"items": []} for video_id in ids},
    )
    request = SearchRequest(keyword="PV5", start_date=date(2026,1,1), end_date=date(2026,8,16),
        selected_sources=[Source.YOUTUBE], max_results=8)
    result = YouTubeCollector(http=http, settings=Settings(youtube_max_videos=8,
        youtube_comments_per_video=2, youtube_max_search_windows=12), api_key="test-key").collect(
            request, ["PV5 日本", "キア PV5"])
    search_calls = [params for url, params in http.calls if url.endswith("/search")]
    assert result.status is CollectorStatus.SUCCESS
    assert len(search_calls) == 8
    assert search_calls[0]["publishedAfter"].startswith("2025-12-31T15:00:00")
    assert search_calls[-1]["publishedBefore"].startswith("2026-08-16T15:00:00")
    assert result.metadata["unique_videos"] == 8


def test_comments_success_uses_comment_date_and_parent_link() -> None:
    http = FakeHttp(
        search=[search_payload("v1")],
        videos={"items": [video_item("v1")]},
        comments={"v1": {"items": [comment_item("c1", "欲しい")] }},
    )
    result = collector(http, max_videos=1).collect(make_request(1), ["PV5 日本"])
    assert result.status is CollectorStatus.SUCCESS
    comment = next(record for record in result.records if record.content_group is ContentGroup.CONSUMER_VOICE)
    assert comment.native_id == "c1"
    assert comment.parent_id == "youtube:video:v1"
    assert comment.published_at.isoformat() == "2026-08-11T04:00:00+00:00"
    assert comment.engagement_count == 7
    assert comment.eligible_for_analysis is True


def test_comments_follow_pagination_until_exhausted_and_record_audit() -> None:
    first = {"items": [comment_item(f"c{i}") for i in range(1, 101)], "nextPageToken": "page-2"}
    second = {"items": [comment_item(f"c{i}") for i in range(101, 121)]}
    http = FakeHttp(search=[search_payload("v1")], videos={"items": [video_item("v1")]},
        comments={"v1": [first, second]})
    result = YouTubeCollector(http=http, settings=Settings(youtube_max_videos=1,
        youtube_comment_safety_limit=1000, youtube_comment_max_pages=20), api_key="test-key").collect(
            make_request(1), ["PV5 日本"])
    comments = [r for r in result.records if r.content_group is ContentGroup.CONSUMER_VOICE]
    audit = result.metadata["video_comment_audit"][0]
    assert len(comments) == 120
    assert result.metadata["comment_api_calls"] == 2
    assert audit["raw_comments_collected"] == audit["comments_after_dedup"] == 120
    assert audit["displayed_comment_count"] == 66
    assert audit["collection_stop_reason"] == "pagination_exhausted"


def test_comments_disabled_skips_video_comments_without_failing_collector() -> None:
    disabled = ExternalServiceError(
        ErrorType.PERMISSION_ERROR,
        "Comments are disabled",
        status_code=403,
        details={"reason": "commentsDisabled"},
    )
    http = FakeHttp(
        search=[search_payload("v1")],
        videos={"items": [video_item("v1")]},
        comments={"v1": disabled},
    )
    result = collector(http, max_videos=1).collect(make_request(1), ["PV5 日本"])
    assert result.status is CollectorStatus.SUCCESS
    assert result.records_collected == 1


def test_quota_and_timeout_errors_become_failed_results() -> None:
    for error_type in (ErrorType.QUOTA_EXCEEDED, ErrorType.RATE_LIMITED, ErrorType.TIMEOUT):
        error = ExternalServiceError(error_type, "safe failure")
        result = collector(FakeHttp(search=[error]), max_videos=1).collect(
            make_request(1), ["PV5 日本"]
        )
        assert result.status is CollectorStatus.FAILED
        assert result.error_type == error_type.value


def test_malformed_response_becomes_failed_result() -> None:
    result = collector(FakeHttp(search=[{"unexpected": []}]), max_videos=1).collect(
        make_request(1), ["PV5 日本"]
    )
    assert result.status is CollectorStatus.FAILED
    assert result.error_type == ErrorType.MALFORMED_RESPONSE.value


def test_foreign_video_is_returned_for_audit_but_comments_are_not_requested() -> None:
    http = FakeHttp(
        search=[search_payload("us1")],
        videos={"items": [video_item("us1", "Kia PV5 USA Review", "Review for American drivers")]},
    )
    result = collector(http, max_videos=1).collect(make_request(1), ["PV5 日本"])
    assert result.status is CollectorStatus.SUCCESS
    assert result.records_collected == 1
    assert result.records[0].eligible_for_analysis is False
    assert not any(url.endswith("/commentThreads") for url, _ in http.calls)


def test_partial_video_comment_failure_preserves_other_video_records() -> None:
    timeout = ExternalServiceError(ErrorType.TIMEOUT, "comment timeout")
    http = FakeHttp(
        search=[search_payload("v1", "v2")],
        videos={"items": [video_item("v1"), video_item("v2")]},
        comments={
            "v1": timeout,
            "v2": {"items": [comment_item("c2")]},
        },
    )
    result = collector(http).collect(make_request(), ["PV5 日本"])
    assert result.status is CollectorStatus.PARTIAL
    assert result.error_type == ErrorType.TIMEOUT.value
    assert {record.native_id for record in result.records} == {"v1", "v2", "c2"}
    assert result.metadata["partial_errors"] == 1


def test_missing_api_key_is_authentication_failure_without_http_calls() -> None:
    http = FakeHttp()
    result = YouTubeCollector(http=http, settings=Settings(), api_key="").collect(  # type: ignore[arg-type]
        make_request(1), ["PV5 日本"]
    )
    assert result.status is CollectorStatus.FAILED
    assert result.error_type == ErrorType.AUTHENTICATION_ERROR.value
    assert http.calls == []
