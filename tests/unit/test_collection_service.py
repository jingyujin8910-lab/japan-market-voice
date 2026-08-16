from datetime import date, datetime, timezone
from typing import List, Sequence

from japan_voice.application.collection_service import CollectionOrchestrator
from japan_voice.collectors.base import CollectorResult
from japan_voice.domain.enums import CollectorStatus, ContentType, Source
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest


def request(*sources: Source) -> SearchRequest:
    return SearchRequest(
        keyword="PV5",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 15),
        selected_sources=list(sources),
        max_results=10,
    )


def item(source: Source, record_id: str) -> ContentRecord:
    return ContentRecord(
        id=record_id,
        source=source,
        provider=f"fake-{source.value}",
        content_type=ContentType.ARTICLE,
        keyword="PV5",
        title="PV5 日本発売",
        published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        url=f"https://example.com/{record_id}",
    )


class FakeSuccessCollector:
    def __init__(self, source: Source, record_ids: Sequence[str]) -> None:
        self.source = source
        self.record_ids = record_ids
        self.received_queries: List[str] = []

    def collect(self, search_request: SearchRequest, queries: Sequence[str]) -> CollectorResult:
        self.received_queries = list(queries)
        records = [item(self.source, record_id) for record_id in self.record_ids]
        return CollectorResult.success(self.source, records[: search_request.max_results])


class FakeFailingCollector:
    source = Source.NEWS

    def collect(self, search_request: SearchRequest, queries: Sequence[str]) -> CollectorResult:
        raise TimeoutError("upstream timed out")


def test_collector_success_is_preserved() -> None:
    collector = FakeSuccessCollector(Source.YOUTUBE, ["video-1"])
    run = CollectionOrchestrator([collector], max_queries_per_source=3).collect(
        request(Source.YOUTUBE)
    )
    assert len(run.successful) == 1
    assert not run.failed
    assert run.records_collected == 1
    assert len(collector.received_queries) == 3


def test_collector_exception_becomes_failure_result() -> None:
    run = CollectionOrchestrator([FakeFailingCollector()]).collect(request(Source.NEWS))
    assert len(run.failed) == 1
    assert run.failed[0].error_type == "TimeoutError"
    assert run.failed[0].error_message == "upstream timed out"
    assert run.records == []


def test_partial_failure_does_not_discard_successful_source() -> None:
    youtube = FakeSuccessCollector(Source.YOUTUBE, ["video-1", "video-2"])
    run = CollectionOrchestrator([youtube, FakeFailingCollector()]).collect(
        request(Source.YOUTUBE, Source.NEWS)
    )
    assert [result.status for result in run.results] == [
        CollectorStatus.SUCCESS, CollectorStatus.FAILED
    ]
    assert [record.id for record in run.records] == ["video-1", "video-2"]
    assert run.records_collected == 2


def test_multiple_collectors_are_aggregated_in_requested_source_order() -> None:
    news = FakeSuccessCollector(Source.NEWS, ["article-1"])
    youtube = FakeSuccessCollector(Source.YOUTUBE, ["video-1", "video-2"])
    run = CollectionOrchestrator([youtube, news]).collect(
        request(Source.NEWS, Source.YOUTUBE)
    )
    assert [result.source for result in run.results] == [Source.NEWS, Source.YOUTUBE]
    assert [record.id for record in run.records] == ["article-1", "video-1", "video-2"]
    assert run.records_collected == 3


def test_missing_collector_is_a_source_local_failure() -> None:
    run = CollectionOrchestrator([]).collect(request(Source.X))
    assert run.failed[0].source is Source.X
    assert run.failed[0].error_type == "CollectorNotConfiguredError"


def test_invalid_collector_result_is_isolated() -> None:
    class WrongSourceCollector(FakeSuccessCollector):
        def collect(self, search_request: SearchRequest, queries: Sequence[str]) -> CollectorResult:
            return CollectorResult.success(Source.NEWS, [item(Source.NEWS, "wrong")])

    run = CollectionOrchestrator([WrongSourceCollector(Source.YOUTUBE, [])]).collect(
        request(Source.YOUTUBE)
    )
    assert run.failed[0].error_type == "ValueError"

