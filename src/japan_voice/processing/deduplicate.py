"""Stable duplicate detection using native ID, URL, then scoped text hash."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from japan_voice.domain.enums import ContentType, ExclusionReason
from japan_voice.domain.records import ContentRecord
from .normalize import canonicalize_url, normalized_text_hash


def deduplicate(records: Iterable[ContentRecord]) -> Tuple[List[ContentRecord], int]:
    seen_native: Dict[tuple, str] = {}
    seen_url: Dict[tuple, str] = {}
    seen_text: Dict[tuple, str] = {}
    output: List[ContentRecord] = []
    duplicates = 0

    for original in records:
        record = original.model_copy(deep=True)
        duplicate_of = None
        native_key = (record.source.value, record.native_id) if record.native_id else None
        # Do not collapse identical short voices from different parents.
        child_voice = record.is_comment or (
            bool(record.parent_id) and record.content_type is ContentType.ANSWER
        )
        url_key = (
            record.source.value,
            record.parent_id if child_voice else None,
            canonicalize_url(str(record.url)),
        )
        hash_input = record.content if child_voice else " ".join(
            value for value in (record.title, record.content) if value
        )
        text_key = (
            record.source.value,
            record.parent_id if child_voice else None,
            normalized_text_hash(hash_input),
        )

        if native_key:
            if native_key in seen_native:
                duplicate_of = seen_native[native_key]
            elif url_key in seen_url:
                duplicate_of = seen_url[url_key]
            elif not child_voice and text_key in seen_text:
                duplicate_of = seen_text[text_key]
        elif url_key in seen_url:
            duplicate_of = seen_url[url_key]
        elif text_key in seen_text:
            duplicate_of = seen_text[text_key]

        if duplicate_of:
            record.eligible_for_analysis = False
            record.duplicate_of = duplicate_of
            record.exclusion_reason = ExclusionReason.DUPLICATE
            duplicates += 1
        else:
            if native_key:
                seen_native[native_key] = record.id
            seen_url[url_key] = record.id
            seen_text[text_key] = record.id
        output.append(record)
    return output, duplicates
