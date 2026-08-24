from japan_voice.application.video_analyzer import (
    YouTubeVideoAnalyzerCollector, extract_youtube_video_id,
)
from japan_voice.config.settings import Settings
from japan_voice.domain.enums import CollectorStatus, ContentGroup, Sentiment


VIDEO_ID = "abcdefghijk"


def video_payload():
    return {"items":[{"id":VIDEO_ID,"snippet":{"title":"PV5 Review","description":"Review",
        "channelTitle":"Channel","publishedAt":"2026-08-10T01:00:00Z",
        "thumbnails":{"high":{"url":"https://example.com/thumb.jpg"}}},
        "statistics":{"viewCount":"1000","likeCount":"50","commentCount":"120"}}]}


def comment(comment_id, text="Great car!", replies=0):
    return {"id":"thread-"+comment_id,"snippet":{"topLevelComment":{"id":comment_id,
        "snippet":{"textOriginal":text,"publishedAt":"2026-08-11T01:00:00Z",
        "likeCount":2,"authorDisplayName":"viewer"}}, "totalReplyCount":replies}}


def reply(comment_id, text):
    return {"id":comment_id,"snippet":{"textOriginal":text,"publishedAt":"2026-08-11T02:00:00Z",
        "likeCount":1,"authorDisplayName":"reply-user"}}


class FakeHttp:
    def __init__(self):
        self.calls=[]
    def get_json(self,url,*,params=None,headers=None):
        self.calls.append((url,dict(params or {})))
        if url.endswith("/videos"): return video_payload()
        if params.get("pageToken") == "p2": return {"items":[comment("c2","日本でも欲しい")]}
        return {"items":[comment("c1")],"nextPageToken":"p2"}


def test_extract_supported_youtube_urls_and_reject_non_youtube():
    assert extract_youtube_video_id(f"https://www.youtube.com/watch?v={VIDEO_ID}") == VIDEO_ID
    assert extract_youtube_video_id(f"https://youtu.be/{VIDEO_ID}") == VIDEO_ID
    assert extract_youtube_video_id(f"https://youtube.com/shorts/{VIDEO_ID}") == VIDEO_ID
    assert extract_youtube_video_id(f"https://youtube.com/live/{VIDEO_ID}?si=share") == VIDEO_ID
    assert extract_youtube_video_id(f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}") == VIDEO_ID
    try:
        extract_youtube_video_id(f"https://example.com/watch?v={VIDEO_ID}")
    except ValueError:
        pass
    else:
        raise AssertionError("non-YouTube URL must be rejected")


def test_direct_analyzer_paginates_and_bypasses_language_and_market_guardrails():
    http=FakeHttp()
    run=YouTubeVideoAnalyzerCollector(http=http,settings=Settings(
        youtube_analyzer_comment_limit=500,youtube_analyzer_max_pages=20),api_key="key").collect(VIDEO_ID)
    assert run.collector_results[0].status is CollectorStatus.SUCCESS
    assert len(run.market_content_records) == 1
    assert len(run.consumer_voice_records) == 2
    assert all(r.content_group is ContentGroup.CONSUMER_VOICE and r.eligible_for_analysis
        for r in run.consumer_voice_records)
    assert run.consumer_voice_records[0].content == "Great car!"
    assert run.collector_results[0].metadata["collection_stop_reason"] == "pagination_exhausted"
    assert len([call for call in http.calls if call[0].endswith("/commentThreads")]) == 2
    assert run.market_content_records[0].raw_metadata["thumbnail"] == "https://example.com/thumb.jpg"


def test_direct_analyzer_collects_all_paginated_replies():
    class ReplyHttp:
        def __init__(self): self.calls=[]
        def get_json(self,url,*,params=None,headers=None):
            self.calls.append((url,dict(params or {})))
            if url.endswith("/videos"): return video_payload()
            if url.endswith("/commentThreads"):
                return {"items":[comment("top", "親コメント", replies=3)]}
            if params.get("pageToken") == "reply-2":
                return {"items":[reply("r3", "三番目の返信")]}
            return {"items":[reply("r1", "first reply"),reply("r2", "二番目の返信")],
                "nextPageToken":"reply-2"}
    run=YouTubeVideoAnalyzerCollector(http=ReplyHttp(),settings=Settings(
        youtube_analyzer_comment_limit=500,youtube_analyzer_max_pages=100),api_key="key").collect(VIDEO_ID)
    assert len(run.consumer_voice_records) == 4
    metadata=run.collector_results[0].metadata
    assert metadata["top_level_comments_collected"] == 1
    assert metadata["replies_collected"] == 3
    assert sum(r.raw_metadata.get("is_reply",False) for r in run.consumer_voice_records) == 3
    assert all(r.raw_metadata.get("translation_required") for r in run.consumer_voice_records)


def test_direct_analyzer_default_limit_allows_one_thousand_comments():
    assert Settings().youtube_analyzer_comment_limit == 1000
