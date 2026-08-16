"""Deterministic collection-to-analysis-dataset processing pipeline."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from japan_voice.application.collection_service import CollectionRunResult
from japan_voice.domain.enums import (
    ContentGroup,
    EntityMatch,
    ExclusionReason,
    Language,
    ScopeDecision,
)
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest
from japan_voice.processing.deduplicate import deduplicate
from japan_voice.processing.guardrails import evaluate_record
from japan_voice.processing.normalize import canonicalize_url, normalize_text
from .models import AuditMetrics, RunResult


def _normalize_record(record: ContentRecord) -> ContentRecord:
    title = normalize_text(record.title or "") or None
    content = normalize_text(record.content)
    updates = {
        "title": title,
        "content": content,
        "keyword": normalize_text(record.keyword),
        "query_used": normalize_text(record.query_used),
        "url": canonicalize_url(str(record.url)),
        "parent_url": canonicalize_url(str(record.parent_url)) if record.parent_url else None,
        # A previously processed collector record must be safe to process again.
        "duplicate_of": None,
        "exclusion_reason": None,
        "eligible_for_analysis": False,
    }
    return record.model_copy(update=updates, deep=True)


def _empty_content(record: ContentRecord) -> bool:
    return not (record.title or record.content)


def _apply_guardrails(records: Iterable[ContentRecord], request: SearchRequest) -> List[ContentRecord]:
    records_list = list(records)
    evaluated: Dict[str, ContentRecord] = {}

    # Parent content must be available before child comments inherit its scope.
    ordered = [record for record in records_list if not record.is_comment]
    ordered.extend(record for record in records_list if record.is_comment)
    for record in ordered:
        if _empty_content(record):
            empty = record.model_copy(
                update={
                    "eligible_for_analysis": False,
                    "exclusion_reason": ExclusionReason.EMPTY_CONTENT,
                },
                deep=True,
            )
            evaluated[record.id] = empty
            continue
        parent: Optional[ContentRecord] = evaluated.get(record.parent_id or "")
        evaluated[record.id] = evaluate_record(
            record,
            start_date=request.start_date,
            end_date=request.end_date,
            parent=parent,
        ).record

    # Restore collector order for raw-data provenance and stable UI tables.
    return [evaluated[record.id] for record in records_list]


def _deduplicate_eligible(records: List[ContentRecord]) -> List[ContentRecord]:
    candidates = [record for record in records if record.eligible_for_analysis]
    deduplicated, _ = deduplicate(candidates)
    by_id = {record.id: record for record in deduplicated}
    return [by_id.get(record.id, record) for record in records]


def _audit(records: List[ContentRecord]) -> AuditMetrics:
    eligible = [record for record in records if record.eligible_for_analysis]
    return AuditMetrics(
        raw_collected=len(records),
        empty_content_excluded=sum(
            record.exclusion_reason is ExclusionReason.EMPTY_CONTENT for record in records
        ),
        entity_excluded=sum(
            record.exclusion_reason in {
                ExclusionReason.ENTITY_UNRELATED,
                ExclusionReason.ENTITY_UNCERTAIN,
            }
            for record in records
        ),
        japan_scope_excluded=sum(
            record.exclusion_reason in {
                ExclusionReason.FOREIGN_MARKET,
                ExclusionReason.SCOPE_AMBIGUOUS,
            }
            for record in records
        ),
        language_excluded=sum(
            record.exclusion_reason in {
                ExclusionReason.NON_JAPANESE,
                ExclusionReason.LANGUAGE_UNKNOWN,
            }
            for record in records
        ),
        date_excluded=sum(
            record.exclusion_reason in {
                ExclusionReason.DATE_OUT_OF_RANGE,
                ExclusionReason.DATE_UNKNOWN,
            }
            for record in records
        ),
        duplicates_removed=sum(
            record.exclusion_reason is ExclusionReason.DUPLICATE for record in records
        ),
        final_eligible=len(eligible),
        consumer_voice_count=sum(
            record.content_group is ContentGroup.CONSUMER_VOICE for record in eligible
        ),
        market_content_count=sum(
            record.content_group is ContentGroup.MARKET_CONTENT for record in eligible
        ),
    )


class ProcessingPipeline:
    def process(
        self,
        collection: CollectionRunResult,
        request: SearchRequest,
        *,
        run_id: Optional[str] = None,
    ) -> RunResult:
        normalized = [_normalize_record(record) for record in collection.records]
        guarded = _apply_guardrails(normalized, request)
        final_records = _deduplicate_eligible(guarded)

        eligible = [record for record in final_records if record.eligible_for_analysis]
        consumer = [
            record for record in eligible
            if record.content_group is ContentGroup.CONSUMER_VOICE
        ]
        market = [
            record for record in eligible
            if record.content_group is ContentGroup.MARKET_CONTENT
        ]
        excluded = [record for record in final_records if not record.eligible_for_analysis]

        return RunResult(
            run_id=run_id or uuid4().hex,
            request=request,
            collector_results=collection.results,
            raw_records=final_records,
            eligible_records=eligible,
            consumer_voice_records=consumer,
            market_content_records=market,
            excluded_records=excluded,
            audit=_audit(final_records),
        )

