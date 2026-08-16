"""Deterministic entity, Japan-market and Japanese-consumer guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Optional, Sequence, Tuple

from japan_voice.domain.enums import (
    ContentGroup,
    ContentType,
    DateSource,
    EntityMatch,
    ExclusionReason,
    Language,
    MinkaraSubSource,
    Source,
    ScopeDecision,
    ScopeMethod,
    YahooSubSource,
)
from japan_voice.domain.records import ContentRecord
from .dates import evaluate_date
from .language import detect_japanese
from .normalize import normalize_for_match, normalize_text


BRAND_ALIASES = ("kia", "キア")
MODEL_ALIASES = ("pv5", "ev3", "ev4", "ev5", "ev6", "ev9", "pbv")
AUTOMOTIVE_SIGNALS = (
    "自動車", "電気自動車", "商用車", "車", "カーゴ", "cargo", "passenger",
    "vehicle", "automotive", "car", "ev", "発売", "販売", "launch", "sales",
)
JAPAN_SIGNALS = (
    "日本市場", "日本向け", "日本仕様", "日本導入", "日本発売", "国内発売",
    "日本販売", "日本価格", "kia japan", "キアジャパン", "日本の道路",
    "日本の充電", "日本上陸", "日本で", "日本では", "国内", "円", "万円",
    "補助金", "販売店", "ディーラー", "試乗", "納車", "予約", "輸入車", "車中泊",
)
FOREIGN_SIGNALS = (
    "united states", "usa", "america", "american", "米国", "アメリカ", "미국",
    "korea", "korean", "韓国", "한국", "europe", "european", "欧州", "ヨーロッパ",
    "germany", "ドイツ", "china", "中国", "georgia",
)
GLOBAL_ONLY_SIGNALS = ("global operating profit", "global sales", "世界販売", "営業利益")


@dataclass(frozen=True)
class Classification:
    decision: ScopeDecision
    score: float
    reason: str
    matched_signals: Tuple[str, ...] = ()


@dataclass(frozen=True)
class GuardrailResult:
    record: ContentRecord
    needs_ai_review: bool


def _has_ascii_token(text: str, token: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text))


def _matched(text: str, signals: Sequence[str]) -> Tuple[str, ...]:
    matches = []
    for signal in signals:
        normalized = signal.casefold()
        if normalized.isascii() and normalized.isalnum():
            if _has_ascii_token(text, normalized):
                matches.append(signal)
        elif normalized in text:
            matches.append(signal)
    return tuple(matches)


def classify_entity(text: str, keyword: str) -> EntityMatch:
    normalized = normalize_for_match(text)
    normalized_keyword = normalize_for_match(keyword)
    models = _matched(normalized, MODEL_ALIASES)
    brands = _matched(normalized, BRAND_ALIASES)
    automotive = _matched(normalized, AUTOMOTIVE_SIGNALS)

    keyword_present = (
        _has_ascii_token(normalized, normalized_keyword)
        if normalized_keyword.isascii() and normalized_keyword.isalnum()
        else normalized_keyword in normalized
    )
    if models or (brands and automotive):
        return EntityMatch.TARGET
    if keyword_present and normalized_keyword not in BRAND_ALIASES:
        return EntityMatch.TARGET if automotive else EntityMatch.UNCERTAIN
    if brands or keyword_present:
        return EntityMatch.UNCERTAIN
    return EntityMatch.UNRELATED


def classify_japan_scope(text: str) -> Classification:
    normalized = normalize_for_match(text)
    japan = _matched(normalized, JAPAN_SIGNALS)
    # Bare 日本/Japan is meaningful but weaker than market-specific phrases.
    if "日本" in normalized and "日本" not in japan:
        japan += ("日本",)
    if _has_ascii_token(normalized, "japan") and "japan" not in japan:
        japan += ("Japan",)
    foreign = _matched(normalized, FOREIGN_SIGNALS)
    global_only = _matched(normalized, GLOBAL_ONLY_SIGNALS)

    if japan:
        reason = "Japan context found"
        if foreign:
            reason = "Japan is a meaningful part of a foreign-market comparison"
        return Classification(ScopeDecision.INCLUDE, 0.90 if not foreign else 0.85, reason, japan + foreign)
    if foreign:
        return Classification(ScopeDecision.EXCLUDE, 0.05, "Foreign market only; no Japan context", foreign)
    if global_only:
        return Classification(ScopeDecision.EXCLUDE, 0.10, "Global corporate news without Japan context", global_only)
    return Classification(ScopeDecision.AMBIGUOUS, 0.55, "No decisive Japan or foreign-market context")


def _default_content_group(record: ContentRecord) -> ContentGroup:
    if record.is_comment or record.content_type in {
        ContentType.COMMENT, ContentType.POST, ContentType.BLOG, ContentType.REVIEW,
        ContentType.QUESTION, ContentType.ANSWER,
    }:
        return ContentGroup.CONSUMER_VOICE
    return ContentGroup.MARKET_CONTENT


def evaluate_record(
    record: ContentRecord,
    *,
    start_date: date,
    end_date: date,
    parent: Optional[ContentRecord] = None,
) -> GuardrailResult:
    """Apply deterministic P0 guardrails without pretending ambiguous AI work is done."""
    result = record.model_copy(deep=True)
    result.content_group = _default_content_group(result)
    inherited_voice = bool(
        parent
        and result.parent_id
        and result.content_type in {ContentType.COMMENT, ContentType.ANSWER}
    )
    text = normalize_text(" ".join(part for part in (result.title, result.content) if part))
    result.entity_match = classify_entity(text, result.keyword)

    parent_entity = parent.entity_match if parent else None
    if inherited_voice and result.entity_match is not EntityMatch.TARGET and parent_entity is EntityMatch.TARGET:
        result.entity_match = EntityMatch.TARGET

    scope = classify_japan_scope(text)
    if (
        parent
        and result.sub_source is YahooSubSource.NEWS_COMMENT
        and parent.scope_decision is ScopeDecision.EXCLUDE
    ):
        scope = Classification(
            ScopeDecision.EXCLUDE,
            parent.japan_market_score or 0.10,
            "Foreign Yahoo article scope inherited from parent",
        )
        result.scope_method = ScopeMethod.INHERITED
    if inherited_voice and scope.decision is ScopeDecision.AMBIGUOUS and parent:
        if parent.scope_decision is ScopeDecision.INCLUDE:
            scope = Classification(ScopeDecision.INCLUDE, parent.japan_market_score or 0.80, "Japan scope inherited from parent")
            result.scope_method = ScopeMethod.INHERITED
        elif parent.scope_decision is ScopeDecision.EXCLUDE:
            scope = Classification(ScopeDecision.EXCLUDE, parent.japan_market_score or 0.10, "Foreign scope inherited from parent")
            result.scope_method = ScopeMethod.INHERITED

    # Once a YouTube video has passed the strict entity/Japan guardrail, its
    # public top-level comments inherit that context. Comment text is analyzed
    # later and does not need to repeat the product or Japan keywords.
    inherited_youtube_comment = bool(
        inherited_voice and result.source is Source.YOUTUBE and parent
        and parent.eligible_for_analysis
    )
    if inherited_youtube_comment:
        result.entity_match = EntityMatch.TARGET
        scope = Classification(
            ScopeDecision.INCLUDE,
            parent.japan_market_score or 0.80,
            "YouTube parent video entity and Japan scope inherited",
        )
        result.scope_method = ScopeMethod.INHERITED
    if result.scope_method is not ScopeMethod.INHERITED:
        result.scope_method = ScopeMethod.RULE
    result.scope_decision = scope.decision
    result.japan_market_relevant = True if scope.decision is ScopeDecision.INCLUDE else False if scope.decision is ScopeDecision.EXCLUDE else None
    result.japan_market_score = scope.score
    result.japan_scope_reason = scope.reason
    result.language = detect_japanese(result.content or result.title or "")
    # Yahoo News comments retain their actual timestamp separately. When it is
    # unavailable, only the analysis/filtering date inherits the parent article.
    if result.sub_source is YahooSubSource.NEWS_COMMENT:
        if result.published_at is not None:
            result.analysis_date = result.published_at
            result.date_source = DateSource.COMMENT
        elif parent and parent.published_at is not None:
            result.analysis_date = parent.published_at
            result.date_source = DateSource.PARENT_ARTICLE
        else:
            result.analysis_date = None
            result.date_source = DateSource.UNKNOWN
    elif result.sub_source is MinkaraSubSource.COMMENT:
        if result.published_at is not None:
            result.analysis_date = result.published_at
            result.date_source = DateSource.COMMENT
        elif parent and parent.published_at is not None:
            result.analysis_date = parent.published_at
            result.date_source = DateSource.PARENT_POST
        else:
            result.analysis_date = None
            result.date_source = DateSource.UNKNOWN
    else:
        result.analysis_date = result.published_at
    result.date_status, result.date_eligible = evaluate_date(result.analysis_date, start_date, end_date)

    needs_ai_review = result.entity_match is EntityMatch.UNCERTAIN or result.scope_decision is ScopeDecision.AMBIGUOUS
    exclusion: Optional[ExclusionReason] = None
    if result.entity_match is EntityMatch.UNRELATED:
        exclusion = ExclusionReason.ENTITY_UNRELATED
    elif result.entity_match is EntityMatch.UNCERTAIN:
        exclusion = ExclusionReason.ENTITY_UNCERTAIN
    elif result.scope_decision is ScopeDecision.EXCLUDE:
        exclusion = ExclusionReason.FOREIGN_MARKET
    elif result.scope_decision is ScopeDecision.AMBIGUOUS:
        exclusion = ExclusionReason.SCOPE_AMBIGUOUS
    elif result.content_group is ContentGroup.CONSUMER_VOICE and result.language is Language.NON_JA and not inherited_youtube_comment:
        exclusion = ExclusionReason.NON_JAPANESE
    elif result.content_group is ContentGroup.CONSUMER_VOICE and result.language is Language.UNKNOWN and not inherited_youtube_comment:
        exclusion = ExclusionReason.LANGUAGE_UNKNOWN
    elif not result.date_eligible and not (
        result.source is Source.MINKARA and result.analysis_date is None
    ):
        exclusion = ExclusionReason.DATE_UNKNOWN if result.analysis_date is None else ExclusionReason.DATE_OUT_OF_RANGE

    result.exclusion_reason = exclusion
    result.eligible_for_analysis = exclusion is None
    return GuardrailResult(record=result, needs_ai_review=needs_ai_review)
