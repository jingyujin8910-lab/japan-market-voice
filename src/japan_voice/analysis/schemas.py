"""Pydantic schemas intended for future Gemini structured JSON output."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from japan_voice.domain.enums import ContentGroup, EntityMatch, Sentiment, Source


def _clean_unique(values: List[str]) -> List[str]:
    output: List[str] = []
    seen = set()
    for value in values:
        cleaned = " ".join(value.split()).strip()
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            output.append(cleaned)
    return output


class ScopeClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1)
    entity_match: EntityMatch
    japan_market_relevant: bool
    japan_market_score: float = Field(ge=0, le=1)
    content_group: ContentGroup
    reason: str = Field(min_length=1, max_length=500)


class ScopeClassificationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classifications: List[ScopeClassification]

    @model_validator(mode="after")
    def unique_record_ids(self) -> "ScopeClassificationBatch":
        ids = [item.record_id for item in self.classifications]
        if len(ids) != len(set(ids)):
            raise ValueError("scope classification IDs must be unique")
        return self


class RecordAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1)
    sentiment: Sentiment = Sentiment.UNKNOWN
    sentiment_score: Optional[float] = Field(default=None, ge=-1, le=1)
    topics: List[str] = Field(default_factory=list, max_length=10)
    positive_drivers: List[str] = Field(default_factory=list, max_length=5)
    negative_drivers: List[str] = Field(default_factory=list, max_length=5)
    customer_questions: List[str] = Field(default_factory=list, max_length=5)
    purchase_signals: List[str] = Field(default_factory=list, max_length=5)
    purchase_barriers: List[str] = Field(default_factory=list, max_length=5)
    translated_ko: str = Field(default="", max_length=2000)

    @field_validator(
        "topics",
        "positive_drivers",
        "negative_drivers",
        "customer_questions",
        "purchase_signals",
        "purchase_barriers",
    )
    @classmethod
    def clean_lists(cls, values: List[str]) -> List[str]:
        return _clean_unique(values)

    @model_validator(mode="after")
    def score_matches_sentiment(self) -> "RecordAnalysis":
        if self.sentiment is Sentiment.UNKNOWN and self.sentiment_score is not None:
            raise ValueError("unknown sentiment cannot have a score")
        return self


class RecordAnalysisBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analyses: List[RecordAnalysis]

    @model_validator(mode="after")
    def unique_record_ids(self) -> "RecordAnalysisBatch":
        ids = [item.record_id for item in self.analyses]
        if len(ids) != len(set(ids)):
            raise ValueError("record analysis IDs must be unique")
        return self


class EvidenceFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1000)
    evidence_record_ids: List[str] = Field(default_factory=list, max_length=20)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.split()).strip()

    @field_validator("evidence_record_ids")
    @classmethod
    def unique_evidence(cls, values: List[str]) -> List[str]:
        return list(dict.fromkeys(values))


class TopicCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=100)
    count: int = Field(ge=1)
    evidence_record_ids: List[str] = Field(default_factory=list, max_length=20)

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, value: str) -> str:
        return " ".join(value.split()).strip()

    @field_validator("evidence_record_ids")
    @classmethod
    def unique_evidence(cls, values: List[str]) -> List[str]:
        return list(dict.fromkeys(values))


class RepresentativeVoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1)
    quote: str = Field(min_length=1, max_length=1000)
    korean_summary: str = Field(min_length=1, max_length=1000)
    source: Source


class AggregateAnalysis(BaseModel):
    """Model-produced synthesis. Numeric sentiment counts are intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    overall_voice: List[EvidenceFinding] = Field(default_factory=list, max_length=5)
    top_topics: List[TopicCount] = Field(default_factory=list, max_length=20)
    positive_drivers: List[EvidenceFinding] = Field(default_factory=list, max_length=10)
    negative_drivers: List[EvidenceFinding] = Field(default_factory=list, max_length=10)
    customer_questions: List[EvidenceFinding] = Field(default_factory=list, max_length=10)
    purchase_signals: List[EvidenceFinding] = Field(default_factory=list, max_length=10)
    purchase_barriers: List[EvidenceFinding] = Field(default_factory=list, max_length=10)
    representative_voc: List[RepresentativeVoc] = Field(default_factory=list, max_length=10)
    marketing_insights: List[EvidenceFinding] = Field(default_factory=list, max_length=10)
    emerging_issues: List[EvidenceFinding] = Field(default_factory=list, max_length=10)


class SentimentSummary(BaseModel):
    """Python-computed consumer voice sentiment counts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    positive: int = Field(ge=0)
    neutral: int = Field(ge=0)
    negative: int = Field(ge=0)
    unknown: int = Field(ge=0)
    consumer_voice_total: int = Field(ge=0)
    consumer_records_total: int = Field(ge=0)
    known_sentiment_total: int = Field(ge=0)

    @model_validator(mode="after")
    def totals_match(self) -> "SentimentSummary":
        if self.positive + self.neutral + self.negative != self.known_sentiment_total:
            raise ValueError("known sentiment total is inconsistent")
        if self.consumer_voice_total != self.known_sentiment_total:
            raise ValueError("consumer voice total must exclude unknown sentiment")
        if self.known_sentiment_total + self.unknown != self.consumer_records_total:
            raise ValueError("consumer record total is inconsistent")
        return self


class AggregateStatus(str, Enum):
    GEMINI = "gemini"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"
    MINIMUM_FALLBACK = "minimum_fallback"
    NO_CONSUMER_DATA = "no_consumer_data"


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_analyses: List[RecordAnalysis]
    sentiment: SentimentSummary
    aggregate: AggregateAnalysis
    aggregate_available: bool = True
    aggregate_status: AggregateStatus = AggregateStatus.GEMINI
    aggregate_error_type: Optional[str] = None
    invalid_evidence_ids_dropped: int = Field(default=0, ge=0)
    invalid_voc_dropped: int = Field(default=0, ge=0)
    analyzed_records: int = Field(ge=0)
    eligible_records: int = Field(ge=0)

    @model_validator(mode="after")
    def coverage_matches(self) -> "AnalysisResult":
        if self.analyzed_records != len(self.record_analyses):
            raise ValueError("analyzed_records does not match record analyses")
        if self.analyzed_records > self.eligible_records:
            raise ValueError("analysis coverage cannot exceed eligible records")
        return self
