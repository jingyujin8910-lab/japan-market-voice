from datetime import date, datetime, timezone
from typing import List, Sequence

from japan_voice.application.collection_service import CollectionOrchestrator, CollectionRunResult
from japan_voice.application.pipeline import ProcessingPipeline
from japan_voice.collectors.base import CollectorResult
from japan_voice.domain.enums import (
    CollectorStatus,
    ContentGroup,
    ContentType,
    ExclusionReason,
    Source,
)
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest


PUBLISHED = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)


def request(*sources: Source) -> SearchRequest:
    return SearchRequest(
        keyword="PV5",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 15),
        selected_sources=list(sources),
        max_results=20,
    )


def record(
    record_id: str,
    title: str,
    *,
    source: Source = Source.YOUTUBE,
    content: str = "",
    content_type: ContentType = ContentType.VIDEO,
    published_at: datetime = PUBLISHED,
    native_id: str = "",
    parent_id: str = "",
    url: str = "",
) -> ContentRecord:
    return ContentRecord(
        id=record_id,
        source=source,
        provider="fixture",
        content_type=content_type,
        keyword="PV5",
        native_id=native_id or record_id,
        parent_id=parent_id or None,
        title=title or None,
        content=content,
        published_at=published_at,
        url=url or f"https://example.com/{record_id}",
        parent_url="https://example.com/video" if parent_id else None,
        is_comment=content_type is ContentType.COMMENT,
    )


def test_pipeline_partitions_youtube_fixture_and_builds_audit_metrics() -> None:
    japan_video = record("jp-video", "  Kia PV5 日本発売  ")
    short_comment = record(
        "jp-comment", "Kia PV5 日本発売", content=" 欲しい ",
        content_type=ContentType.COMMENT, parent_id="jp-video",
    )
    foreign = record("us-video", "Kia PV5 launches in the United States")
    unrelated = record("unrelated", "Tokyo weather forecast")
    out_of_date = record(
        "old", "Kia PV5 日本発売", published_at=datetime(2026, 7, 1, tzinfo=timezone.utc)
    )
    duplicate = record(
        "jp-video-copy", "Kia PV5 日本発売", native_id="jp-video",
        url="https://example.com/different",
    )
    collection = CollectionRunResult(
        results=[
            CollectorResult.success(
                Source.YOUTUBE,
                [japan_video, short_comment, foreign, unrelated, out_of_date, duplicate],
            )
        ]
    )

    result = ProcessingPipeline().process(collection, request(Source.YOUTUBE), run_id="run-1")

    assert result.run_id == "run-1"
    assert len(result.raw_records) == 6
    assert {item.id for item in result.eligible_records} == {"jp-video", "jp-comment"}
    assert [item.id for item in result.consumer_voice_records] == ["jp-comment"]
    assert [item.id for item in result.market_content_records] == ["jp-video"]
    assert len(result.excluded_records) == 4
    assert result.audit.model_dump() == {
        "raw_collected": 6,
        "empty_content_excluded": 0,
        "entity_excluded": 1,
        "japan_scope_excluded": 1,
        "language_excluded": 0,
        "date_excluded": 1,
        "duplicates_removed": 1,
        "final_eligible": 2,
        "consumer_voice_count": 1,
        "market_content_count": 1,
    }
    normalized_comment = next(item for item in result.raw_records if item.id == "jp-comment")
    assert normalized_comment.content == "欲しい"


class FakeCollector:
    def __init__(self, source: Source, records: Sequence[ContentRecord]) -> None:
        self.source = source
        self.records = list(records)

    def collect(self, search_request: SearchRequest, queries: Sequence[str]) -> CollectorResult:
        return CollectorResult.success(self.source, self.records)


class PartialCollector:
    source = Source.NEWS

    def collect(self, search_request: SearchRequest, queries: Sequence[str]) -> CollectorResult:
        error = TimeoutError("one upstream page timed out")
        return CollectorResult.partial(
            self.source,
            [
                record(
                    "news-jp", "Kia PV5 日本市場に導入", source=Source.NEWS,
                    content_type=ContentType.ARTICLE,
                )
            ],
            error,
        )


def test_pipeline_preserves_partial_source_status_and_aggregates_collectors() -> None:
    search_request = request(Source.YOUTUBE, Source.NEWS)
    youtube = FakeCollector(
        Source.YOUTUBE,
        [record("video", "Kia PV5 日本発売")],
    )
    collection = CollectionOrchestrator([youtube, PartialCollector()]).collect(search_request)
    result = ProcessingPipeline().process(collection, search_request)

    assert [item.status for item in result.collector_results] == [
        CollectorStatus.SUCCESS,
        CollectorStatus.PARTIAL,
    ]
    assert result.audit.raw_collected == 2
    assert result.audit.final_eligible == 2
    assert result.audit.market_content_count == 2


def test_pipeline_is_idempotent_for_preguarded_youtube_records() -> None:
    search_request = request(Source.YOUTUBE)
    first_collection = CollectionRunResult(
        results=[
            CollectorResult.success(
                Source.YOUTUBE,
                [
                    record("video", "Kia PV5 日本発売"),
                    record(
                        "comment", "Kia PV5 日本発売", content="欲しい",
                        content_type=ContentType.COMMENT, parent_id="video",
                    ),
                ],
            )
        ]
    )
    first = ProcessingPipeline().process(first_collection, search_request)
    second_collection = CollectionRunResult(
        results=[CollectorResult.success(Source.YOUTUBE, first.raw_records)]
    )
    second = ProcessingPipeline().process(second_collection, search_request)

    assert [item.eligible_for_analysis for item in second.raw_records] == [True, True]
    assert second.audit == first.audit


def test_pipeline_preserves_public_comment_from_eligible_youtube_parent() -> None:
    parent = record("video", "Kia PV5 日本発売")
    english = record(
        "comment", "Kia PV5 日本発売", content="Great car!",
        content_type=ContentType.COMMENT, parent_id="video",
    )
    collection = CollectionRunResult(
        results=[CollectorResult.success(Source.YOUTUBE, [parent, english])]
    )
    result = ProcessingPipeline().process(collection, request(Source.YOUTUBE))
    included = next(item for item in result.consumer_voice_records if item.id == "comment")
    assert included.exclusion_reason is None
    assert included.eligible_for_analysis is True
    assert result.audit.language_excluded == 0
    assert result.audit.final_eligible == 2
