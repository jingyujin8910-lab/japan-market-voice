from datetime import date, datetime, timezone

from japan_voice.analysis.schemas import (
    AggregateAnalysis, AggregateStatus, AnalysisResult, RecordAnalysis, SentimentSummary,
)
from japan_voice.application.collection_service import CollectionRunResult
from japan_voice.application.pipeline import ProcessingPipeline
from japan_voice.collectors.base import CollectorResult
from japan_voice.domain.enums import ContentType, Sentiment, Source
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest
from japan_voice.ui.metrics import dashboard_metrics, youtube_video_audit


def _run_and_analysis():
    published = datetime(2026, 8, 10, tzinfo=timezone.utc)
    video = ContentRecord(id="video", source=Source.YOUTUBE, provider="YouTube",
        content_type=ContentType.VIDEO, keyword="PV5", title="PV5 日本発売", published_at=published,
        url="https://youtube.com/watch?v=v")
    comments = [ContentRecord(id=f"c{i}", source=Source.YOUTUBE, provider="YouTube",
        content_type=ContentType.COMMENT, keyword="PV5", title=video.title, content="デザインいいね",
        native_id=f"c{i}",
        parent_id=video.id, parent_url=video.url, published_at=published,
        url=f"https://youtube.com/watch?v=v&lc=c{i}", is_comment=True) for i in range(4)]
    request = SearchRequest(keyword="PV5", start_date=date(2026,8,1), end_date=date(2026,8,16),
        selected_sources=[Source.YOUTUBE], max_results=5)
    result = CollectorResult.success(Source.YOUTUBE, [video] + comments)
    result.metadata = {"video_comment_audit":[{"video_id":None, "displayed_comment_count":66,
        "raw_comments_collected":4, "comments_after_dedup":4,
        "collection_stop_reason":"pagination_exhausted"}]}
    run = ProcessingPipeline().process(CollectionRunResult([result]), request)
    analyses = [RecordAnalysis(record_id="video", sentiment=Sentiment.UNKNOWN)] + [
        RecordAnalysis(record_id=f"c{i}", sentiment=value, topics=["충전"])
        for i, value in enumerate((Sentiment.POSITIVE, Sentiment.NEGATIVE, Sentiment.NEUTRAL, Sentiment.UNKNOWN))
    ]
    analysis = AnalysisResult(record_analyses=analyses,
        sentiment=SentimentSummary(positive=1,negative=1,neutral=1,unknown=1,
            consumer_voice_total=3,consumer_records_total=4,known_sentiment_total=3),
        aggregate=AggregateAnalysis(), aggregate_available=True,
        aggregate_status=AggregateStatus.MINIMUM_FALLBACK, analyzed_records=5, eligible_records=5)
    return run, analysis


def test_dashboard_populations_and_source_invariants_are_consistent() -> None:
    run, analysis = _run_and_analysis()
    metrics = dashboard_metrics(run, analysis)
    assert metrics.total_records == 5
    assert metrics.consumer_voices == metrics.positive + metrics.negative + metrics.neutral == 3
    assert metrics.unknown == 1
    assert sum(metrics.voices_by_source.values()) == metrics.consumer_voices
    assert metrics.voices_by_source[Source.YOUTUBE] == 3
    assert metrics.topics["충전 인프라"] == 3
    assert metrics.warnings == []


def test_youtube_detail_voice_count_matches_overview_and_audit_invariants() -> None:
    run, analysis = _run_and_analysis()
    metrics = dashboard_metrics(run, analysis)
    audit = youtube_video_audit(run, analysis)[0]
    assert audit["raw_comments_collected"] >= audit["comments_after_dedup"]
    assert audit["comments_after_dedup"] == (
        audit["positive_count"] + audit["negative_count"] + audit["neutral_count"] + audit["unknown_count"]
    )
    assert audit["consumer_voice_count"] == metrics.voices_by_source[Source.YOUTUBE] == 3
    assert audit["warnings"] == []
