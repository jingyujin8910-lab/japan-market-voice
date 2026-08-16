"""Application result models for processed collection runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, ConfigDict, Field, model_validator

from japan_voice.collectors.base import CollectorResult
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest


class AuditMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_collected: int = Field(ge=0)
    empty_content_excluded: int = Field(default=0, ge=0)
    entity_excluded: int = Field(ge=0)
    japan_scope_excluded: int = Field(ge=0)
    language_excluded: int = Field(default=0, ge=0)
    date_excluded: int = Field(ge=0)
    duplicates_removed: int = Field(ge=0)
    final_eligible: int = Field(ge=0)
    consumer_voice_count: int = Field(ge=0)
    market_content_count: int = Field(ge=0)

    @model_validator(mode="after")
    def eligible_groups_match(self) -> "AuditMetrics":
        if self.final_eligible != self.consumer_voice_count + self.market_content_count:
            raise ValueError("final_eligible must equal consumer_voice + market_content")
        return self


class RunResult(BaseModel):
    """One immutable snapshot suitable for a later session-state/UI layer."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    request: SearchRequest
    collector_results: List[CollectorResult]
    raw_records: List[ContentRecord]
    eligible_records: List[ContentRecord]
    consumer_voice_records: List[ContentRecord]
    market_content_records: List[ContentRecord]
    excluded_records: List[ContentRecord]
    audit: AuditMetrics
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def dataset_counts_match(self) -> "RunResult":
        if self.completed_at.tzinfo is None or self.completed_at.utcoffset() is None:
            raise ValueError("completed_at must be timezone-aware")
        if len(self.raw_records) != self.audit.raw_collected:
            raise ValueError("raw_records count does not match audit")
        if len(self.eligible_records) != self.audit.final_eligible:
            raise ValueError("eligible_records count does not match audit")
        if len(self.excluded_records) + len(self.eligible_records) != len(self.raw_records):
            raise ValueError("eligible and excluded datasets must partition raw_records")
        return self

