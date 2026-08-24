"""Direct single-YouTube-video collection without market discovery guardrails."""

from __future__ import annotations

from datetime import date
import re
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from japan_voice.application.models import AuditMetrics, RunResult
from japan_voice.collectors.base import CollectorResult
from japan_voice.collectors.youtube import YOUTUBE_API_BASE, _items, _parse_datetime
from japan_voice.config.settings import Settings
from japan_voice.domain.enums import (
    CollectorStatus, ContentGroup, ContentType, DateSource, DateStatus,
    EntityMatch, Language, ScopeDecision, ScopeMethod, Source,
)
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError
from japan_voice.infrastructure.http import HttpClient
from japan_voice.processing.deduplicate import deduplicate


_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_youtube_video_id(value: str) -> str:
    """Accept canonical, short, Shorts, and embed YouTube URLs only."""
    try:
        parsed = urlsplit(value.strip())
    except ValueError as error:
        raise ValueError("올바른 YouTube URL을 입력해주세요.") from error
    host = (parsed.hostname or "").lower()
    candidate = ""
    if host in {
        "youtube.com", "www.youtube.com", "m.youtube.com",
        "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com",
    }:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}:
                candidate = parts[1]
    elif host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    if parsed.scheme not in {"http", "https"} or not _VIDEO_ID.fullmatch(candidate):
        raise ValueError("지원되는 YouTube 영상 URL에서 video_id를 찾을 수 없습니다.")
    return candidate


def _integer(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class YouTubeVideoAnalyzerCollector:
    """Collect one selected video's accessible top-level comments and replies."""

    def __init__(self, *, http: HttpClient, settings: Settings, api_key: Optional[str]) -> None:
        self._http = http
        self._settings = settings
        self._api_key = api_key

    def collect(self, video_id: str) -> RunResult:
        if not self._api_key:
            raise ExternalServiceError(ErrorType.AUTHENTICATION_ERROR, "YOUTUBE_API_KEY is not configured")
        video = self._video(video_id)
        records = [video]
        error: Optional[ExternalServiceError] = None
        calls = 1
        stop_reason = "unknown"
        top_level_count = 0
        reply_count = 0
        try:
            comments, comment_calls, stop_reason, top_level_count, reply_count = self._comments(video)
            records.extend(comments)
            calls += comment_calls
        except ExternalServiceError as caught:
            error = caught
            stop_reason = "comments_disabled" if caught.details.get("reason") == "commentsDisabled" else "collection_error"
        records, duplicates = deduplicate(records)
        eligible = [record for record in records if record.eligible_for_analysis]
        consumers = [record for record in eligible if record.content_group is ContentGroup.CONSUMER_VOICE]
        market = [record for record in eligible if record.content_group is ContentGroup.MARKET_CONTENT]
        metadata = {
            "video_id": video_id,
            "displayed_comment_count": video.raw_metadata.get("displayed_comment_count"),
            "raw_comments_collected": len(records) - 1,
            "comments_after_dedup": len(consumers),
            "top_level_comments_collected": top_level_count,
            "replies_collected": reply_count,
            "collection_stop_reason": stop_reason,
            "api_calls": calls,
        }
        if error:
            result = CollectorResult.partial(Source.YOUTUBE, records, error, metadata=metadata)
        else:
            result = CollectorResult.success(Source.YOUTUBE, records)
            result.metadata = metadata
        request = SearchRequest(
            keyword=video_id, start_date=date(1970, 1, 1), end_date=date(2100, 1, 1),
            selected_sources=[Source.YOUTUBE], max_results=min(1000, self._settings.youtube_analyzer_comment_limit),
        )
        return RunResult(
            run_id=uuid4().hex, request=request, collector_results=[result], raw_records=records,
            eligible_records=eligible, consumer_voice_records=consumers,
            market_content_records=market, excluded_records=[r for r in records if not r.eligible_for_analysis],
            audit=AuditMetrics(
                raw_collected=len(records), duplicates_removed=duplicates, final_eligible=len(eligible),
                consumer_voice_count=len(consumers), market_content_count=len(market),
                entity_excluded=0, japan_scope_excluded=0, date_excluded=0,
            ),
        )

    def _video(self, video_id: str) -> ContentRecord:
        payload = self._http.get_json(f"{YOUTUBE_API_BASE}/videos", params={
            "key": self._api_key, "part": "snippet,statistics", "id": video_id,
        })
        items = _items(payload, "videos")
        if not items:
            raise ExternalServiceError(ErrorType.NO_DATA, "YouTube 영상을 찾을 수 없거나 공개 접근이 불가능합니다.")
        item = items[0]
        snippet, statistics = item.get("snippet"), item.get("statistics", {})
        if not isinstance(snippet, dict) or not isinstance(statistics, dict):
            raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "YouTube video metadata is malformed")
        thumbnails = snippet.get("thumbnails") or {}
        thumbnail = next((thumbnails[key].get("url") for key in ("maxres", "standard", "high", "medium", "default")
            if isinstance(thumbnails.get(key), dict) and thumbnails[key].get("url")), None)
        published = _parse_datetime(snippet.get("publishedAt"))
        return ContentRecord(
            id=f"youtube:video:{video_id}", source=Source.YOUTUBE, provider="YouTube",
            native_id=video_id, content_type=ContentType.VIDEO, content_group=ContentGroup.MARKET_CONTENT,
            keyword=video_id, title=str(snippet.get("title") or ""), content=str(snippet.get("description") or ""),
            author=str(snippet.get("channelTitle") or "") or None, published_at=published,
            analysis_date=published, date_source=DateSource.UNKNOWN, date_status=DateStatus.KNOWN,
            url=f"https://www.youtube.com/watch?v={video_id}", entity_match=EntityMatch.TARGET,
            japan_market_relevant=True, japan_market_score=1, japan_scope_reason="user_selected_video",
            scope_decision=ScopeDecision.INCLUDE, scope_method=ScopeMethod.INHERITED,
            date_eligible=True, eligible_for_analysis=True,
            raw_metadata={"thumbnail": thumbnail, "view_count": _integer(statistics.get("viewCount")),
                "like_count": _integer(statistics.get("likeCount")),
                "displayed_comment_count": _integer(statistics.get("commentCount"))},
        )

    def _comments(self, parent: ContentRecord):
        records: List[ContentRecord] = []
        calls = 0
        token: Optional[str] = None
        stop_reason = "unknown"
        top_level_count = 0
        reply_count = 0
        while calls < self._settings.youtube_analyzer_max_pages:
            remaining = self._settings.youtube_analyzer_comment_limit - len(records)
            if remaining <= 0:
                stop_reason = "technical_safety_limit"; break
            params: Dict[str, Any] = {"key": self._api_key, "part": "snippet", "videoId": parent.native_id,
                "order": "time", "textFormat": "plainText", "maxResults": min(100, remaining)}
            if token: params["pageToken"] = token
            payload = self._http.get_json(f"{YOUTUBE_API_BASE}/commentThreads", params=params)
            calls += 1
            page = _items(payload, "comments")
            for thread in page:
                top = thread.get("snippet", {}).get("topLevelComment", {})
                snippet = top.get("snippet") if isinstance(top, dict) else None
                comment_id = top.get("id") if isinstance(top, dict) else None
                if not isinstance(comment_id, str) or not isinstance(snippet, dict):
                    raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "YouTube comment item is malformed")
                text = snippet.get("textOriginal") or snippet.get("textDisplay")
                if not isinstance(text, str) or not text.strip(): continue
                records.append(self._comment_record(parent, comment_id, snippet, is_reply=False))
                top_level_count += 1
                total_replies = _integer(thread.get("snippet", {}).get("totalReplyCount")) or 0
                if total_replies and len(records) < self._settings.youtube_analyzer_comment_limit:
                    replies, reply_calls, reply_complete = self._replies(
                        parent, comment_id,
                        self._settings.youtube_analyzer_comment_limit - len(records),
                        self._settings.youtube_analyzer_max_pages - calls,
                    )
                    records.extend(replies)
                    reply_count += len(replies)
                    calls += reply_calls
                    if not reply_complete:
                        stop_reason = "technical_safety_limit"
                        break
                if len(records) >= self._settings.youtube_analyzer_comment_limit: break
            if stop_reason == "technical_safety_limit": break
            token = payload.get("nextPageToken")
            if not token:
                stop_reason = "no_comments" if calls == 1 and not page else "pagination_exhausted"; break
        else:
            stop_reason = "technical_safety_limit"
        return records, calls, stop_reason, top_level_count, reply_count

    def _replies(self, parent: ContentRecord, top_comment_id: str, remaining: int, page_budget: int):
        records: List[ContentRecord] = []
        calls = 0
        token: Optional[str] = None
        complete = False
        while calls < page_budget and len(records) < remaining:
            params: Dict[str, Any] = {"key": self._api_key, "part": "snippet", "parentId": top_comment_id,
                "textFormat": "plainText", "maxResults": min(100, remaining - len(records))}
            if token: params["pageToken"] = token
            payload = self._http.get_json(f"{YOUTUBE_API_BASE}/comments", params=params)
            calls += 1
            for item in _items(payload, "replies"):
                comment_id, snippet = item.get("id"), item.get("snippet")
                if not isinstance(comment_id, str) or not isinstance(snippet, dict):
                    raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "YouTube reply item is malformed")
                text = snippet.get("textOriginal") or snippet.get("textDisplay")
                if isinstance(text, str) and text.strip():
                    records.append(self._comment_record(parent, comment_id, snippet, is_reply=True,
                        top_comment_id=top_comment_id))
                if len(records) >= remaining: break
            token = payload.get("nextPageToken")
            if not token:
                complete = True; break
        return records, calls, complete

    @staticmethod
    def _comment_record(parent: ContentRecord, comment_id: str, snippet: Mapping[str, Any], *,
                        is_reply: bool, top_comment_id: Optional[str] = None) -> ContentRecord:
        published = _parse_datetime(snippet.get("publishedAt"))
        return ContentRecord(
            id=f"youtube:comment:{comment_id}", source=Source.YOUTUBE, provider="YouTube",
            native_id=comment_id, parent_id=parent.id, content_type=ContentType.COMMENT,
            content_group=ContentGroup.CONSUMER_VOICE, keyword=parent.native_id or "video",
            title=parent.title, content=str(snippet.get("textOriginal") or snippet.get("textDisplay") or ""),
            author=str(snippet.get("authorDisplayName") or "") or None,
            published_at=published, analysis_date=published, date_source=DateSource.COMMENT,
            date_status=DateStatus.KNOWN, url=f"{parent.url}&lc={comment_id}", parent_url=parent.url,
            engagement_count=int(snippet.get("likeCount") or 0), language=Language.UNKNOWN, is_comment=True,
            entity_match=EntityMatch.TARGET, japan_market_relevant=True, japan_market_score=1,
            japan_scope_reason="user_selected_video_comment", scope_decision=ScopeDecision.INCLUDE,
            scope_method=ScopeMethod.INHERITED, date_eligible=True, eligible_for_analysis=True,
            raw_metadata={"translation_required": True, "is_reply": is_reply,
                "top_comment_id": top_comment_id},
        )
