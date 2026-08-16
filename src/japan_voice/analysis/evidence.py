"""Server-side reconciliation of model evidence against eligible records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from japan_voice.domain.enums import ContentGroup
from japan_voice.domain.records import ContentRecord
from japan_voice.processing.normalize import normalize_text
from .schemas import AggregateAnalysis, EvidenceFinding


class AnalysisValidationError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceReconciliationAudit:
    invalid_evidence_ids_dropped: int = 0
    invalid_voc_dropped: int = 0


def reconcile_aggregate_evidence(
    aggregate: AggregateAnalysis,
    records: Iterable[ContentRecord],
) -> Tuple[AggregateAnalysis, EvidenceReconciliationAudit]:
    by_id: Dict[str, ContentRecord] = {record.id: record for record in records}
    allowed = set(by_id)
    consumer_ids = {
        record.id for record in by_id.values()
        if record.content_group is ContentGroup.CONSUMER_VOICE
    }

    invalid_ids = 0

    def keep_known(ids: Iterable[str], permitted: Set[str]) -> List[str]:
        nonlocal invalid_ids
        values = list(ids)
        kept = [record_id for record_id in values if record_id in permitted]
        invalid_ids += len(values) - len(kept)
        return kept

    for topic in aggregate.top_topics:
        topic.evidence_record_ids = keep_known(topic.evidence_record_ids, allowed)

    consumer_findings: List[EvidenceFinding] = (
        aggregate.positive_drivers
        + aggregate.negative_drivers
        + aggregate.customer_questions
        + aggregate.purchase_signals
        + aggregate.purchase_barriers
    )
    for finding in consumer_findings:
        finding.evidence_record_ids = keep_known(finding.evidence_record_ids, consumer_ids)

    for finding in (
        aggregate.overall_voice + aggregate.marketing_insights + aggregate.emerging_issues
    ):
        finding.evidence_record_ids = keep_known(finding.evidence_record_ids, allowed)

    valid_voc = []
    invalid_voc = 0
    for voc in aggregate.representative_voc:
        record = by_id.get(voc.record_id)
        if record is None or voc.record_id not in consumer_ids or voc.source is not record.source:
            invalid_voc += 1
            continue
        quote = normalize_text(voc.quote)
        original = normalize_text(record.content)
        if not quote or quote not in original:
            invalid_voc += 1
            continue
        valid_voc.append(voc)
    aggregate.representative_voc = valid_voc
    return aggregate, EvidenceReconciliationAudit(
        invalid_evidence_ids_dropped=invalid_ids,
        invalid_voc_dropped=invalid_voc,
    )


def validate_aggregate_evidence(
    aggregate: AggregateAnalysis,
    records: Iterable[ContentRecord],
) -> None:
    """Compatibility wrapper; reconciliation now accepts valid partial output."""
    reconcile_aggregate_evidence(aggregate, records)
