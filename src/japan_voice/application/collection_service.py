"""Independent, partial-failure-safe source collection orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping

from japan_voice.collectors.base import Collector, CollectorResult
from japan_voice.domain.enums import CollectorStatus, Source
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest
from .query_planner import expand_japan_queries


class CollectorNotConfiguredError(LookupError):
    pass


@dataclass(frozen=True)
class CollectionRunResult:
    results: List[CollectorResult]

    @property
    def records(self) -> List[ContentRecord]:
        return [record for result in self.results for record in result.records]

    @property
    def successful(self) -> List[CollectorResult]:
        return [
            result for result in self.results
            if result.status in {CollectorStatus.SUCCESS, CollectorStatus.PARTIAL}
        ]

    @property
    def failed(self) -> List[CollectorResult]:
        return [result for result in self.results if result.status is CollectorStatus.FAILED]

    @property
    def records_collected(self) -> int:
        return sum(result.records_collected for result in self.results)


class CollectionOrchestrator:
    def __init__(self, collectors: Iterable[Collector], *, max_queries_per_source: int = 5) -> None:
        if max_queries_per_source <= 0:
            raise ValueError("max_queries_per_source must be positive")
        registry: Dict[Source, Collector] = {}
        for collector in collectors:
            if collector.source in registry:
                raise ValueError(f"duplicate collector for source: {collector.source.value}")
            registry[collector.source] = collector
        self._collectors: Mapping[Source, Collector] = registry
        self._max_queries = max_queries_per_source

    def collect(self, request: SearchRequest) -> CollectionRunResult:
        results: List[CollectorResult] = []
        for source in request.selected_sources:
            collector = self._collectors.get(source)
            if collector is None:
                results.append(
                    CollectorResult.failure(
                        source,
                        CollectorNotConfiguredError(f"No collector configured for {source.value}"),
                    )
                )
                continue

            queries = expand_japan_queries(
                request.keyword,
                source,
                max_queries=self._max_queries,
            )
            try:
                result = collector.collect(request, queries)
                if result.source is not source:
                    raise ValueError(
                        f"Collector for {source.value} returned source {result.source.value}"
                    )
                results.append(result)
            except Exception as error:
                # Collector boundaries convert all source-local failures to data.
                results.append(CollectorResult.failure(source, error))
        return CollectionRunResult(results=results)
