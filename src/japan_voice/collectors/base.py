"""Source-independent collector protocol and result envelope."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from japan_voice.domain.enums import CollectorStatus, Source
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest


class CollectorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Source
    status: CollectorStatus
    records: List[ContentRecord] = Field(default_factory=list)
    records_collected: int = Field(default=0, ge=0)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_result(self) -> "CollectorResult":
        if self.collected_at.tzinfo is None or self.collected_at.utcoffset() is None:
            raise ValueError("collected_at must be timezone-aware")
        if self.records_collected != len(self.records):
            raise ValueError("records_collected must equal len(records)")
        if any(record.source is not self.source for record in self.records):
            raise ValueError("all records must belong to the result source")
        if self.status is CollectorStatus.SUCCESS and (self.error_type or self.error_message):
            raise ValueError("successful results cannot contain errors")
        if self.status is CollectorStatus.FAILED and not self.error_type:
            raise ValueError("failed results require error_type")
        if self.status is CollectorStatus.FAILED and self.records:
            raise ValueError("failed results cannot contain records")
        if self.status is CollectorStatus.PARTIAL and not self.error_type:
            raise ValueError("partial results require error_type")
        return self

    @classmethod
    def success(cls, source: Source, records: Sequence[ContentRecord]) -> "CollectorResult":
        items = list(records)
        return cls(
            source=source,
            status=CollectorStatus.SUCCESS,
            records=items,
            records_collected=len(items),
        )

    @classmethod
    def failure(cls, source: Source, error: Exception) -> "CollectorResult":
        message = str(error).strip() or "Collector failed"
        return cls(
            source=source,
            status=CollectorStatus.FAILED,
            error_type=getattr(error, "error_type", type(error).__name__),
            error_message=message,
        )

    @classmethod
    def partial(
        cls,
        source: Source,
        records: Sequence[ContentRecord],
        error: Exception,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "CollectorResult":
        items = list(records)
        return cls(
            source=source,
            status=CollectorStatus.PARTIAL,
            records=items,
            records_collected=len(items),
            error_type=getattr(error, "error_type", type(error).__name__),
            error_message=str(error).strip() or "Collector partially failed",
            metadata=metadata or {},
        )


@runtime_checkable
class Collector(Protocol):
    """A source collector. Implementations must not mutate SearchRequest."""

    source: Source

    def collect(self, request: SearchRequest, queries: Sequence[str]) -> CollectorResult:
        ...
