"""Typed runtime settings with environment/Streamlit secret resolution."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping, Optional


def _streamlit_secrets() -> Mapping[str, Any]:
    """Return Streamlit secrets when running in Streamlit, otherwise empty."""
    try:
        import streamlit as st  # Imported lazily; core/tests do not require Streamlit.

        # Materialize the lazy proxy here so a missing secrets.toml is handled
        # before it escapes into callers. Local development may use `.env`.
        return dict(st.secrets)
    except Exception:
        return {}


def get_secret(
    name: str,
    *,
    environ: Optional[Mapping[str, str]] = None,
    streamlit_secrets: Optional[Mapping[str, Any]] = None,
) -> Optional[str]:
    """Resolve a secret from environment first, then Streamlit secrets.

    Empty and whitespace-only values are treated as missing. Secret values are
    never logged or interpolated into error messages here.
    """
    env = os.environ if environ is None else environ
    value = env.get(name)
    if value is not None and str(value).strip():
        return str(value).strip()

    secrets = _streamlit_secrets() if streamlit_secrets is None else streamlit_secrets
    try:
        value = secrets.get(name)
    except (AttributeError, KeyError, TypeError):
        value = None
    return str(value).strip() if value is not None and str(value).strip() else None


def _integer(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None or not raw.strip() else int(raw)


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None or not raw.strip() else float(raw)


@dataclass(frozen=True)
class Settings:
    gemini_model: str = "gemini-2.5-flash"
    youtube_max_videos: int = 20
    youtube_comments_per_video: int = 50
    youtube_max_search_windows: int = 36
    youtube_comment_safety_limit: int = 1000
    youtube_comment_max_pages: int = 20
    youtube_analyzer_comment_limit: int = 100
    youtube_analyzer_max_pages: int = 100
    x_max_posts: int = 100
    gemini_batch_size: int = 30
    gemini_max_attempts: int = 2
    gemini_retry_base_seconds: float = 0.5
    gemini_retry_max_seconds: float = 4.0
    default_date_range_days: int = 30
    request_timeout_seconds: float = 20.0
    http_connect_timeout_seconds: float = 5.0
    http_read_timeout_seconds: float = 15.0
    http_max_retries: int = 2
    http_backoff_base_seconds: float = 0.25
    http_backoff_max_seconds: float = 4.0
    cache_ttl_seconds: int = 3600
    max_query_variants_per_source: int = 5
    yahoo_max_queries: int = 3
    yahoo_news_articles_per_query: int = 10
    yahoo_comments_per_article: int = 500
    yahoo_comment_max_pages: int = 50
    yahoo_questions_per_query: int = 10
    yahoo_answers_per_question: int = 10
    minkara_max_queries: int = 3
    minkara_posts_per_query: int = 10
    minkara_comments_per_post: int = 20
    japan_market_include_threshold: float = 0.75
    japan_market_review_threshold: float = 0.50

    def __post_init__(self) -> None:
        positive = {
            "youtube_max_videos": self.youtube_max_videos,
            "youtube_comments_per_video": self.youtube_comments_per_video,
            "youtube_max_search_windows": self.youtube_max_search_windows,
            "youtube_comment_safety_limit": self.youtube_comment_safety_limit,
            "youtube_comment_max_pages": self.youtube_comment_max_pages,
            "youtube_analyzer_comment_limit": self.youtube_analyzer_comment_limit,
            "youtube_analyzer_max_pages": self.youtube_analyzer_max_pages,
            "x_max_posts": self.x_max_posts,
            "gemini_batch_size": self.gemini_batch_size,
            "gemini_max_attempts": self.gemini_max_attempts,
            "gemini_retry_base_seconds": self.gemini_retry_base_seconds,
            "gemini_retry_max_seconds": self.gemini_retry_max_seconds,
            "default_date_range_days": self.default_date_range_days,
            "request_timeout_seconds": self.request_timeout_seconds,
            "http_connect_timeout_seconds": self.http_connect_timeout_seconds,
            "http_read_timeout_seconds": self.http_read_timeout_seconds,
            "http_backoff_base_seconds": self.http_backoff_base_seconds,
            "http_backoff_max_seconds": self.http_backoff_max_seconds,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "max_query_variants_per_source": self.max_query_variants_per_source,
            "yahoo_max_queries": self.yahoo_max_queries,
            "yahoo_news_articles_per_query": self.yahoo_news_articles_per_query,
            "yahoo_comments_per_article": self.yahoo_comments_per_article,
            "yahoo_comment_max_pages": self.yahoo_comment_max_pages,
            "yahoo_questions_per_query": self.yahoo_questions_per_query,
            "yahoo_answers_per_question": self.yahoo_answers_per_question,
            "minkara_max_queries": self.minkara_max_queries,
            "minkara_posts_per_query": self.minkara_posts_per_query,
            "minkara_comments_per_post": self.minkara_comments_per_post,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.http_max_retries < 0:
            raise ValueError("http_max_retries must not be negative")
        if not 1 <= self.gemini_max_attempts <= 2:
            raise ValueError("gemini_max_attempts must be between 1 and 2")
        if not 0 <= self.japan_market_review_threshold <= self.japan_market_include_threshold <= 1:
            raise ValueError("Japan market thresholds must satisfy 0 <= review <= include <= 1")


def load_settings(*, load_dotenv_file: bool = True) -> Settings:
    """Load non-secret settings. `.env` loading is local-development only."""
    if load_dotenv_file:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass

    return Settings(
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        youtube_max_videos=_integer("YOUTUBE_MAX_VIDEOS", 20),
        youtube_comments_per_video=_integer("YOUTUBE_COMMENTS_PER_VIDEO", 50),
        youtube_max_search_windows=_integer("YOUTUBE_MAX_SEARCH_WINDOWS", 36),
        youtube_comment_safety_limit=_integer("YOUTUBE_COMMENT_SAFETY_LIMIT", 1000),
        youtube_comment_max_pages=_integer("YOUTUBE_COMMENT_MAX_PAGES", 20),
        youtube_analyzer_comment_limit=_integer("YOUTUBE_ANALYZER_COMMENT_LIMIT", 100),
        youtube_analyzer_max_pages=_integer("YOUTUBE_ANALYZER_MAX_PAGES", 100),
        x_max_posts=_integer("X_MAX_POSTS", 100),
        gemini_batch_size=_integer("GEMINI_BATCH_SIZE", 30),
        gemini_max_attempts=_integer("GEMINI_MAX_ATTEMPTS", 2),
        gemini_retry_base_seconds=_float("GEMINI_RETRY_BASE_SECONDS", 0.5),
        gemini_retry_max_seconds=_float("GEMINI_RETRY_MAX_SECONDS", 4.0),
        default_date_range_days=_integer("DEFAULT_DATE_RANGE_DAYS", 30),
        request_timeout_seconds=_float("REQUEST_TIMEOUT_SECONDS", 20.0),
        http_connect_timeout_seconds=_float("HTTP_CONNECT_TIMEOUT_SECONDS", 5.0),
        http_read_timeout_seconds=_float("HTTP_READ_TIMEOUT_SECONDS", 15.0),
        http_max_retries=_integer("HTTP_MAX_RETRIES", 2),
        http_backoff_base_seconds=_float("HTTP_BACKOFF_BASE_SECONDS", 0.25),
        http_backoff_max_seconds=_float("HTTP_BACKOFF_MAX_SECONDS", 4.0),
        cache_ttl_seconds=_integer("CACHE_TTL_SECONDS", 3600),
        max_query_variants_per_source=_integer("MAX_QUERY_VARIANTS_PER_SOURCE", 5),
        yahoo_max_queries=_integer("YAHOO_MAX_QUERIES", 3),
        yahoo_news_articles_per_query=_integer("YAHOO_NEWS_ARTICLES_PER_QUERY", 10),
        yahoo_comments_per_article=_integer("YAHOO_COMMENTS_PER_ARTICLE", 500),
        yahoo_comment_max_pages=_integer("YAHOO_COMMENT_MAX_PAGES", 50),
        yahoo_questions_per_query=_integer("YAHOO_QUESTIONS_PER_QUERY", 10),
        yahoo_answers_per_question=_integer("YAHOO_ANSWERS_PER_QUESTION", 10),
        minkara_max_queries=_integer("MINKARA_MAX_QUERIES", 3),
        minkara_posts_per_query=_integer("MINKARA_POSTS_PER_QUERY", 10),
        minkara_comments_per_post=_integer("MINKARA_COMMENTS_PER_POST", 20),
        japan_market_include_threshold=_float("JAPAN_MARKET_INCLUDE_THRESHOLD", 0.75),
        japan_market_review_threshold=_float("JAPAN_MARKET_REVIEW_THRESHOLD", 0.50),
    )
