"""Canonical enums shared by collectors, processing and later UI layers."""

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class Source(StrEnum):
    YOUTUBE = "youtube"
    YAHOO = "yahoo"
    YAHOO_JAPAN = "yahoo_japan"
    NEWS = "news"
    X = "x"
    MINKARA = "minkara"
    WEB = "web"


class ContentType(StrEnum):
    VIDEO = "video"
    COMMENT = "comment"
    ARTICLE = "article"
    POST = "post"
    BLOG = "blog"
    REVIEW = "review"
    QUESTION = "question"
    ANSWER = "answer"


class YahooSubSource(StrEnum):
    NEWS_ARTICLE = "yahoo_news_article"
    NEWS_COMMENT = "yahoo_news_comment"
    CHIEBUKURO_QUESTION = "yahoo_chiebukuro_question"
    CHIEBUKURO_ANSWER = "yahoo_chiebukuro_answer"
    REALTIME_POST = "yahoo_realtime_post"


class MinkaraSubSource(StrEnum):
    POST = "minkara_post"
    COMMENT = "minkara_comment"


class ContentGroup(StrEnum):
    MARKET_CONTENT = "market_content"
    CONSUMER_VOICE = "consumer_voice"
    UNKNOWN = "unknown"


class Language(StrEnum):
    JA = "ja"
    NON_JA = "non_ja"
    UNKNOWN = "unknown"


class EntityMatch(StrEnum):
    TARGET = "target"
    UNRELATED = "unrelated"
    UNCERTAIN = "uncertain"


class ScopeDecision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    AMBIGUOUS = "ambiguous"


class ScopeMethod(StrEnum):
    RULE = "rule"
    GEMINI = "gemini"
    INHERITED = "inherited"
    NONE = "none"


class DateStatus(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    INVALID = "invalid"


class DateSource(StrEnum):
    COMMENT = "comment"
    PARENT_ARTICLE = "parent_article"
    PARENT_POST = "parent_post"
    UNKNOWN = "unknown"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class ExclusionReason(StrEnum):
    ENTITY_UNRELATED = "entity_unrelated"
    ENTITY_UNCERTAIN = "entity_uncertain"
    FOREIGN_MARKET = "foreign_market"
    SCOPE_AMBIGUOUS = "scope_ambiguous"
    NON_JAPANESE = "non_japanese"
    LANGUAGE_UNKNOWN = "language_unknown"
    DATE_OUT_OF_RANGE = "date_out_of_range"
    DATE_UNKNOWN = "date_unknown"
    DUPLICATE = "duplicate"
    EMPTY_CONTENT = "empty_content"


class CollectorStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
