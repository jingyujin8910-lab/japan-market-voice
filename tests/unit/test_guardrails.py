from datetime import date, datetime, timezone
from typing import Optional

import pytest

from japan_voice.domain.enums import ContentType, EntityMatch, ScopeDecision, Source
from japan_voice.domain.records import ContentRecord
from japan_voice.processing.guardrails import classify_entity, classify_japan_scope, evaluate_record


START = date(2026, 8, 1)
END = date(2026, 8, 15)
PUBLISHED = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)


def record(
    record_id: str,
    title: str,
    *,
    source: Source = Source.NEWS,
    content: str = "",
    content_type: ContentType = ContentType.ARTICLE,
    keyword: str = "KIA",
    parent_id: Optional[str] = None,
) -> ContentRecord:
    return ContentRecord(
        id=record_id,
        source=source,
        provider="test-provider",
        content_type=content_type,
        keyword=keyword,
        title=title,
        content=content,
        published_at=PUBLISHED,
        url=f"https://example.com/{record_id}",
        parent_id=parent_id,
        is_comment=content_type is ContentType.COMMENT,
    )


@pytest.mark.parametrize(
    ("record_value", "expected"),
    [
        (record("us", "Kia PV5 launches in the United States", keyword="PV5"), ScopeDecision.EXCLUDE),
        (record("kr", "韓国でKia PV5販売開始", keyword="PV5"), ScopeDecision.EXCLUDE),
        (record("jp", "キアPV5、日本で販売開始", keyword="PV5"), ScopeDecision.INCLUDE),
        (record("compare", "Kia PV5は韓国で販売済みだが、日本発売はいつ？", keyword="PV5"), ScopeDecision.INCLUDE),
        (
            record("yahoo-us", "キア、米国市場で販売記録更新", source=Source.YAHOO),
            ScopeDecision.EXCLUDE,
        ),
        (
            record("yahoo-jp", "キアPV5、日本市場に正式導入", source=Source.YAHOO, keyword="PV5"),
            ScopeDecision.INCLUDE,
        ),
    ],
)
def test_prd_article_scope_cases(record_value: ContentRecord, expected: ScopeDecision) -> None:
    result = evaluate_record(record_value, start_date=START, end_date=END).record
    assert result.scope_decision is expected
    assert result.eligible_for_analysis is (expected is ScopeDecision.INCLUDE)


def test_japanese_short_comment_on_japan_youtube_video_is_included() -> None:
    parent = evaluate_record(
        record("jp-video", "Kia PV5 日本発売解説", source=Source.YOUTUBE, content_type=ContentType.VIDEO, keyword="PV5"),
        start_date=START,
        end_date=END,
    ).record
    comment = record(
        "jp-comment", "", source=Source.YOUTUBE, content="欲しい",
        content_type=ContentType.COMMENT, keyword="PV5", parent_id=parent.id,
    )
    result = evaluate_record(comment, start_date=START, end_date=END, parent=parent).record
    assert result.scope_decision is ScopeDecision.INCLUDE
    assert result.entity_match is EntityMatch.TARGET
    assert result.eligible_for_analysis is True


def test_prd_exact_foreign_market_comparison_is_japan_scope() -> None:
    """Scope classification is independent from target-entity classification."""
    result = classify_japan_scope("韓国では販売済みだが、日本発売はいつ？")
    assert result.decision is ScopeDecision.INCLUDE


def test_kia_entity_disambiguation_uses_token_and_automotive_context() -> None:
    assert classify_entity("Kia PV5 日本発売", "KIA") is EntityMatch.TARGET
    assert classify_entity("Saskia won an award", "KIA") is EntityMatch.UNRELATED
    assert classify_entity("KIA announces an update", "KIA") is EntityMatch.UNCERTAIN


@pytest.mark.parametrize("text", ["PV5", "キア PV5", "PV5 Cargo"])
def test_pv5_is_a_deterministic_kia_vehicle_entity(text: str) -> None:
    assert classify_entity(text, "PV5") is EntityMatch.TARGET


def test_pv5_token_boundary_and_kia_strictness_are_preserved() -> None:
    assert classify_entity("APV5X is an unrelated product", "PV5") is EntityMatch.UNRELATED
    assert classify_entity("KIA announces an update", "KIA") is EntityMatch.UNCERTAIN


def test_japanese_launch_request_on_global_youtube_video_is_included() -> None:
    parent = evaluate_record(
        record("global-video", "Kia PV5 Global Reveal", source=Source.YOUTUBE, content_type=ContentType.VIDEO, keyword="PV5"),
        start_date=START,
        end_date=END,
    ).record
    comment = record(
        "global-jp-comment", "", source=Source.YOUTUBE, content="日本でも売ってほしい",
        content_type=ContentType.COMMENT, keyword="PV5", parent_id=parent.id,
    )
    result = evaluate_record(comment, start_date=START, end_date=END, parent=parent).record
    assert result.scope_decision is ScopeDecision.INCLUDE
    assert result.entity_match is EntityMatch.TARGET
    assert result.eligible_for_analysis is True


def test_english_comment_on_us_youtube_video_is_excluded() -> None:
    parent = evaluate_record(
        record("us-video", "Kia PV5 USA Review", source=Source.YOUTUBE, content_type=ContentType.VIDEO, keyword="PV5"),
        start_date=START,
        end_date=END,
    ).record
    comment = record(
        "us-comment", "", source=Source.YOUTUBE, content="Great car!",
        content_type=ContentType.COMMENT, keyword="PV5", parent_id=parent.id,
    )
    result = evaluate_record(comment, start_date=START, end_date=END, parent=parent).record
    assert result.scope_decision is ScopeDecision.EXCLUDE
    assert result.eligible_for_analysis is False


def test_minkara_japanese_vehicle_voice_is_included() -> None:
    item = record(
        "minkara", "", source=Source.MINKARA, content="PV5は車中泊に使いやすそう",
        content_type=ContentType.REVIEW, keyword="PV5",
    )
    result = evaluate_record(item, start_date=START, end_date=END).record
    assert result.scope_decision is ScopeDecision.INCLUDE
    assert result.eligible_for_analysis is True
