"""Bounded synchronous micro-batching for interactive analysis."""

from __future__ import annotations

from typing import Iterable, List

from japan_voice.domain.records import ContentRecord


def _record_chars(record: ContentRecord) -> int:
    return len(record.title or "") + len(record.content)


def split_record_batches(
    records: Iterable[ContentRecord],
    *,
    max_records: int,
    max_chars: int,
) -> List[List[ContentRecord]]:
    if max_records <= 0 or max_chars <= 0:
        raise ValueError("batch limits must be positive")
    batches: List[List[ContentRecord]] = []
    current: List[ContentRecord] = []
    current_chars = 0
    for record in records:
        size = _record_chars(record)
        if current and (len(current) >= max_records or current_chars + size > max_chars):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(record)
        current_chars += size
        # A single oversized record remains a bounded one-record batch for the
        # caller to truncate or reject at the provider boundary later.
        if len(current) >= max_records or current_chars >= max_chars:
            batches.append(current)
            current = []
            current_chars = 0
    if current:
        batches.append(current)
    return batches

