"""Single source of truth for dashboard populations and invariants."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from japan_voice.analysis.schemas import AnalysisResult, RecordAnalysis
from japan_voice.application.models import RunResult
from japan_voice.domain.enums import ContentType, Sentiment, Source


TOPIC_ALIASES = {
    "충전": "충전 인프라", "충전소": "충전 인프라", "충전 시설": "충전 인프라",
    "充電": "충전 인프라", "充電インフラ": "충전 인프라", "充電設備": "충전 인프라",
    "航続距離": "주행거리", "주행 거리": "주행거리", "車中泊": "차박 활용성",
    "차박": "차박 활용성", "価格": "가격", "車両価格": "가격",
}


def normalize_topic(value: str) -> str:
    cleaned = " ".join(value.split()).strip()
    return TOPIC_ALIASES.get(cleaned, cleaned)


@dataclass(frozen=True)
class DashboardMetrics:
    total_records: int
    consumer_voices: int
    positive: int
    negative: int
    neutral: int
    unknown: int
    voices_by_source: Dict[Source, int]
    topics: Counter
    analyses_by_id: Dict[str, RecordAnalysis]
    consumer_record_ids: List[str]
    warnings: List[str] = field(default_factory=list)


def dashboard_metrics(run: RunResult, analysis: Optional[AnalysisResult]) -> DashboardMetrics:
    analyses = {item.record_id: item for item in analysis.record_analyses} if analysis else {}
    consumer_records = [record for record in run.consumer_voice_records if record.id in analyses]
    known = [record for record in consumer_records if analyses[record.id].sentiment in {
        Sentiment.POSITIVE, Sentiment.NEGATIVE, Sentiment.NEUTRAL,
    }]
    counts = Counter(analyses[record.id].sentiment for record in consumer_records)
    by_source = Counter(record.source for record in known)
    topics = Counter(
        normalize_topic(topic)
        for record in known for topic in analyses[record.id].topics
        if normalize_topic(topic)
    )
    warnings: List[str] = []
    voices = counts[Sentiment.POSITIVE] + counts[Sentiment.NEGATIVE] + counts[Sentiment.NEUTRAL]
    if voices != len(known):
        warnings.append("consumer_voice_sentiment_total_mismatch")
    if sum(by_source.values()) != voices:
        warnings.append("voice_by_source_total_mismatch")
    if analysis and analysis.sentiment.consumer_voice_total != voices:
        warnings.append("analysis_consumer_voice_total_mismatch")
    return DashboardMetrics(
        total_records=len(run.eligible_records), consumer_voices=voices,
        positive=counts[Sentiment.POSITIVE], negative=counts[Sentiment.NEGATIVE],
        neutral=counts[Sentiment.NEUTRAL], unknown=counts[Sentiment.UNKNOWN],
        voices_by_source=dict(by_source), topics=topics, analyses_by_id=analyses,
        consumer_record_ids=[record.id for record in known], warnings=warnings,
    )


def youtube_video_audit(run: RunResult, analysis: Optional[AnalysisResult]) -> List[Dict[str, object]]:
    metrics = dashboard_metrics(run, analysis)
    raw_comments = [r for r in run.raw_records if r.source is Source.YOUTUBE and r.content_type is ContentType.COMMENT]
    videos = [r for r in run.eligible_records if r.source is Source.YOUTUBE and r.content_type is ContentType.VIDEO]
    collector_audit = {}
    for result in run.collector_results:
        if result.source is Source.YOUTUBE:
            collector_audit = {item.get("video_id"): item for item in result.metadata.get("video_comment_audit", [])}
    output = []
    for video in videos:
        comments = [r for r in raw_comments if r.parent_id == video.id]
        after_dedup = [r for r in comments if not r.duplicate_of and r.eligible_for_analysis]
        analyzed = [metrics.analyses_by_id[r.id] for r in after_dedup if r.id in metrics.analyses_by_id]
        sentiments = Counter(item.sentiment for item in analyzed)
        known = sentiments[Sentiment.POSITIVE] + sentiments[Sentiment.NEGATIVE] + sentiments[Sentiment.NEUTRAL]
        base = collector_audit.get(video.native_id, {})
        warnings = []
        if len(comments) < len(after_dedup): warnings.append("raw_lt_after_dedup")
        if analyzed and len(after_dedup) != sum(sentiments.values()): warnings.append("analysis_coverage_mismatch")
        if known > len(after_dedup): warnings.append("consumer_voice_gt_after_dedup")
        output.append({
            "video_id": video.native_id, "video_title": video.title or "",
            "video_published_at": video.published_at,
            "displayed_comment_count": base.get("displayed_comment_count", video.raw_metadata.get("displayed_comment_count")),
            "raw_comments_collected": len(comments), "comments_after_dedup": len(after_dedup),
            "positive_count": sentiments[Sentiment.POSITIVE], "negative_count": sentiments[Sentiment.NEGATIVE],
            "neutral_count": sentiments[Sentiment.NEUTRAL], "unknown_count": sentiments[Sentiment.UNKNOWN],
            "consumer_voice_count": known,
            "collection_stop_reason": base.get("collection_stop_reason", "unknown"),
            "warnings": warnings,
        })
    return output
