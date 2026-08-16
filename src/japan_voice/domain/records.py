"""Pydantic common record schema from PRD sections 6 and 82."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from .enums import (
    ContentGroup,
    ContentType,
    DateSource,
    DateStatus,
    EntityMatch,
    ExclusionReason,
    Language,
    MinkaraSubSource,
    ScopeDecision,
    ScopeMethod,
    Sentiment,
    Source,
    YahooSubSource,
)


class ContentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(min_length=1)
    source: Source
    sub_source: Optional[Union[YahooSubSource, MinkaraSubSource]] = None
    provider: str = Field(min_length=1)
    content_type: ContentType
    content_group: ContentGroup = ContentGroup.UNKNOWN
    keyword: str = Field(min_length=1)
    query_used: str = ""
    native_id: Optional[str] = None
    parent_id: Optional[str] = None
    title: Optional[str] = None
    content: str = ""
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    analysis_date: Optional[datetime] = None
    date_source: DateSource = DateSource.UNKNOWN
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    url: HttpUrl
    parent_url: Optional[HttpUrl] = None
    engagement_count: Optional[int] = Field(default=None, ge=0)
    language: Language = Language.UNKNOWN
    is_comment: bool = False
    entity_match: EntityMatch = EntityMatch.UNCERTAIN
    japan_market_relevant: Optional[bool] = None
    japan_market_score: Optional[float] = Field(default=None, ge=0, le=1)
    japan_scope_reason: Optional[str] = None
    scope_decision: ScopeDecision = ScopeDecision.AMBIGUOUS
    scope_method: ScopeMethod = ScopeMethod.NONE
    date_status: DateStatus = DateStatus.UNKNOWN
    date_eligible: bool = False
    duplicate_of: Optional[str] = None
    exclusion_reason: Optional[ExclusionReason] = None
    eligible_for_analysis: bool = False
    sentiment: Sentiment = Sentiment.UNKNOWN
    sentiment_score: Optional[float] = Field(default=None, ge=-1, le=1)
    topics: List[str] = Field(default_factory=list)
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("published_at", "analysis_date", "collected_at")
    @classmethod
    def timezone_aware(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("datetimes must be timezone-aware")
        return value

    @model_validator(mode="after")
    def record_invariants(self) -> "ContentRecord":
        if not (self.title or self.content).strip():
            raise ValueError("at least one of title or content must contain text")
        if self.is_comment and self.content_type is not ContentType.COMMENT:
            raise ValueError("is_comment records must use content_type=comment")
        if self.duplicate_of and self.eligible_for_analysis:
            raise ValueError("duplicate records cannot be eligible for analysis")
        return self
