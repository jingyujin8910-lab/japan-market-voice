"""Gemini-shaped client protocol plus a no-network deterministic mock."""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Protocol, Sequence, Union, runtime_checkable

from japan_voice.domain.records import ContentRecord
from .schemas import (
    AggregateAnalysis,
    RecordAnalysis,
    RecordAnalysisBatch,
    ScopeClassificationBatch,
)


@runtime_checkable
class GeminiAnalysisClient(Protocol):
    def classify_scope(self, records: Sequence[ContentRecord]) -> ScopeClassificationBatch:
        ...

    def analyze_records(self, records: Sequence[ContentRecord]) -> RecordAnalysisBatch:
        ...

    def synthesize(
        self,
        records: Sequence[ContentRecord],
        analyses: Sequence[RecordAnalysis],
    ) -> AggregateAnalysis:
        ...


class MockGeminiClient:
    """Returns caller-supplied Pydantic data and performs no external calls."""

    def __init__(
        self,
        *,
        batch_outputs: Sequence[Union[RecordAnalysisBatch, dict]],
        aggregate_output: Union[AggregateAnalysis, dict],
        scope_outputs: Optional[Sequence[Union[ScopeClassificationBatch, dict]]] = None,
    ) -> None:
        self._batch_outputs: Deque[Union[RecordAnalysisBatch, dict]] = deque(batch_outputs)
        self._aggregate_output = aggregate_output
        self._scope_outputs: Deque[Union[ScopeClassificationBatch, dict]] = deque(scope_outputs or [])
        self.scope_calls = 0
        self.analyze_calls = 0
        self.synthesize_calls = 0

    def classify_scope(self, records: Sequence[ContentRecord]) -> ScopeClassificationBatch:
        self.scope_calls += 1
        if not self._scope_outputs:
            raise RuntimeError("No mock scope output configured")
        output = self._scope_outputs.popleft()
        return output if isinstance(output, ScopeClassificationBatch) else ScopeClassificationBatch.model_validate(output)

    def analyze_records(self, records: Sequence[ContentRecord]) -> RecordAnalysisBatch:
        self.analyze_calls += 1
        if not self._batch_outputs:
            raise RuntimeError("No mock batch output configured")
        output = self._batch_outputs.popleft()
        return output if isinstance(output, RecordAnalysisBatch) else RecordAnalysisBatch.model_validate(output)

    def synthesize(
        self,
        records: Sequence[ContentRecord],
        analyses: Sequence[RecordAnalysis],
    ) -> AggregateAnalysis:
        self.synthesize_calls += 1
        output = self._aggregate_output
        return output if isinstance(output, AggregateAnalysis) else AggregateAnalysis.model_validate(output)
