from datetime import date, datetime, timezone
from typing import Optional

import pytest
from pydantic import ValidationError

from japan_voice.config.settings import get_secret
from japan_voice.domain.enums import ContentType, DateStatus, Source
from japan_voice.domain.records import ContentRecord
from japan_voice.processing.dates import evaluate_date, jst_bounds
from japan_voice.processing.deduplicate import deduplicate
from japan_voice.processing.language import detect_japanese
from japan_voice.processing.normalize import canonicalize_url, normalize_text


def make_record(
    record_id: str,
    *,
    native_id: Optional[str] = None,
    url: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> ContentRecord:
    return ContentRecord(
        id=record_id,
        source=Source.YOUTUBE,
        provider="youtube",
        content_type=ContentType.COMMENT,
        keyword="PV5",
        native_id=native_id,
        parent_id=parent_id,
        content="欲しい",
        is_comment=True,
        published_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        url=url or f"https://youtube.com/watch?v={record_id}",
    )


def test_normalization_is_nfkc_html_free_and_whitespace_stable() -> None:
    assert normalize_text("  ＫＩＡ\n<b>ＰＶ５</b>  ") == "KIA PV5"


def test_url_normalization_removes_tracking_and_fragment() -> None:
    assert canonicalize_url("HTTPS://Example.COM/a/?utm_source=x&b=2&a=1#top") == "https://example.com/a?a=1&b=2"


def test_jst_date_range_is_inclusive_at_both_calendar_edges() -> None:
    start, end = jst_bounds(date(2026, 8, 1), date(2026, 8, 15))
    assert start == datetime(2026, 7, 31, 15, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 15, 15, tzinfo=timezone.utc)
    assert evaluate_date(start, date(2026, 8, 1), date(2026, 8, 15)) == (DateStatus.KNOWN, True)
    assert evaluate_date(end, date(2026, 8, 1), date(2026, 8, 15)) == (DateStatus.KNOWN, False)


def test_unknown_and_naive_dates_are_not_eligible() -> None:
    assert evaluate_date(None, date(2026, 8, 1), date(2026, 8, 15)) == (DateStatus.UNKNOWN, False)
    assert evaluate_date(datetime(2026, 8, 1), date(2026, 8, 1), date(2026, 8, 15)) == (DateStatus.INVALID, False)


def test_schema_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        ContentRecord(
            id="bad", source=Source.NEWS, provider="news", content_type=ContentType.ARTICLE,
            keyword="PV5", title="PV5 日本発売", published_at=datetime(2026, 8, 1),
            url="https://example.com/bad",
        )


def test_deduplication_prefers_native_id_then_canonical_url() -> None:
    records = [
        make_record("one", native_id="native-1", url="https://youtube.com/watch?v=1&utm_source=x"),
        make_record("two", native_id="native-1", url="https://youtube.com/watch?v=2"),
        make_record("three", native_id="native-3", url="https://youtube.com/watch?v=1"),
    ]
    result, count = deduplicate(records)
    assert count == 2
    assert result[1].duplicate_of == "one"
    assert result[2].duplicate_of == "one"


def test_identical_short_comments_under_different_parents_are_not_text_duplicates() -> None:
    result, count = deduplicate([
        make_record("a", parent_id="video-a"),
        make_record("b", parent_id="video-b"),
    ])
    assert count == 0
    assert all(item.duplicate_of is None for item in result)


def test_language_filter_handles_short_japanese_and_english() -> None:
    assert detect_japanese("欲しい").value == "ja"
    assert detect_japanese("Great car!").value == "non_ja"


def test_secret_resolver_prefers_environment_and_ignores_blanks() -> None:
    assert get_secret("KEY", environ={"KEY": " env "}, streamlit_secrets={"KEY": "cloud"}) == "env"
    assert get_secret("KEY", environ={"KEY": " "}, streamlit_secrets={"KEY": " cloud "}) == "cloud"
    assert get_secret("KEY", environ={}, streamlit_secrets={}) is None
