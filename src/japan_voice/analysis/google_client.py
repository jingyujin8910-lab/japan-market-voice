"""Official google-genai adapter with Pydantic structured output."""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, Optional, Sequence, Type, TypeVar

import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from japan_voice.config.settings import Settings, get_secret
from japan_voice.domain.records import ContentRecord
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError
from .evidence import AnalysisValidationError
from .prompts import aggregate_prompt, record_analysis_prompt, scope_prompt
from .schemas import (
    AggregateAnalysis,
    RecordAnalysis,
    RecordAnalysisBatch,
    ScopeClassificationBatch,
)


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _gemini_json_schema(schema: Type[BaseModel]) -> Dict[str, Any]:
    """Return a Gemini-compatible copy without weakening local validation."""
    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: clean(item)
                for key, item in value.items()
                if key != "additionalProperties"
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(schema.model_json_schema())


def _aggregate_gemini_schema() -> Dict[str, Any]:
    """Small wire schema; Pydantic remains the authoritative validator."""
    evidence = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "evidence_record_ids": {"type": "array", "items": {"type": "string"}},
        },
    }
    topic = {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "count": {"type": "integer"},
            "evidence_record_ids": {"type": "array", "items": {"type": "string"}},
        },
    }
    voc = {
        "type": "object",
        "properties": {
            "record_id": {"type": "string"},
            "quote": {"type": "string"},
            "korean_summary": {"type": "string"},
            "source": {"type": "string"},
        },
    }
    evidence_lists = (
        "overall_voice",
        "positive_drivers",
        "negative_drivers",
        "customer_questions",
        "purchase_signals",
        "purchase_barriers",
        "marketing_insights",
        "emerging_issues",
    )
    properties = {
        name: {"type": "array", "items": evidence} for name in evidence_lists
    }
    properties["top_topics"] = {"type": "array", "items": topic}
    properties["representative_voc"] = {"type": "array", "items": voc}
    return {
        "type": "object",
        "properties": properties,
        # Keep the wire schema simple, but prevent Gemini from satisfying it
        # with an empty object when evidence-rich records were supplied.
        "required": list(properties),
    }


class GoogleGeminiClient:
    """Gemini Developer API adapter. No prompt/content/credential logging."""

    def __init__(
        self,
        *,
        model: str,
        api_key: Optional[str] = None,
        sdk_client: Optional[Any] = None,
        max_attempts: int = 2,
        retry_base_seconds: float = 0.5,
        retry_max_seconds: float = 4.0,
        request_timeout_seconds: float = 20.0,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        if not 1 <= max_attempts <= 2:
            raise ValueError("max_attempts must be between 1 and 2")
        if retry_base_seconds <= 0 or retry_max_seconds <= 0 or request_timeout_seconds <= 0:
            raise ValueError("Gemini timeout and backoff values must be positive")
        resolved_key = api_key if api_key is not None else get_secret("GEMINI_API_KEY")
        if sdk_client is None and not resolved_key:
            raise ExternalServiceError(
                ErrorType.AUTHENTICATION_ERROR,
                "GEMINI_API_KEY is not configured",
            )
        self.model = model
        self._max_attempts = max_attempts
        self._retry_base = retry_base_seconds
        self._retry_max = retry_max_seconds
        self._sleep = sleep
        self._random = random_value
        self._owns_client = sdk_client is None
        self._client = sdk_client or genai.Client(
            api_key=resolved_key,
            http_options=types.HttpOptions(
                timeout=int(request_timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(
                    attempts=1,
                    http_status_codes=[429, 500, 502, 503, 504],
                ),
            ),
        )

    @classmethod
    def from_settings(cls, settings: Settings, *, api_key: Optional[str] = None) -> "GoogleGeminiClient":
        return cls(
            model=settings.gemini_model,
            api_key=api_key,
            max_attempts=settings.gemini_max_attempts,
            retry_base_seconds=settings.gemini_retry_base_seconds,
            retry_max_seconds=settings.gemini_retry_max_seconds,
            request_timeout_seconds=settings.request_timeout_seconds,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def classify_scope(self, records: Sequence[ContentRecord]) -> ScopeClassificationBatch:
        expected = {record.id for record in records}
        def validate(result: ScopeClassificationBatch) -> None:
            actual = {item.record_id for item in result.classifications}
            if actual != expected:
                raise AnalysisValidationError("scope classification IDs do not match requested batch")
        return self._generate(ScopeClassificationBatch, scope_prompt(records), validate=validate)

    def analyze_records(self, records: Sequence[ContentRecord]) -> RecordAnalysisBatch:
        expected = {record.id for record in records}
        translation_required = {
            record.id for record in records if record.raw_metadata.get("translation_required")
        }
        def validate(result: RecordAnalysisBatch) -> None:
            actual = {item.record_id for item in result.analyses}
            if actual != expected:
                raise AnalysisValidationError("record analysis IDs do not match requested batch")
            translations = {item.record_id: item.translated_ko.strip() for item in result.analyses}
            if any(not translations.get(record_id) for record_id in translation_required):
                raise AnalysisValidationError("video analyzer comment translation is missing")
        return self._generate(RecordAnalysisBatch, record_analysis_prompt(records), validate=validate)

    def synthesize(
        self,
        records: Sequence[ContentRecord],
        analyses: Sequence[RecordAnalysis],
    ) -> AggregateAnalysis:
        def require_content(result: AggregateAnalysis) -> None:
            if records and not any(
                getattr(result, field_name)
                for field_name in AggregateAnalysis.model_fields
            ):
                raise AnalysisValidationError("aggregate response contains no insight content")

        return self._generate(
            AggregateAnalysis,
            aggregate_prompt(records, analyses),
            validate=require_content,
            response_schema=_aggregate_gemini_schema(),
        )

    def _generate(
        self,
        schema: Type[SchemaT],
        prompt: str,
        *,
        validate: Optional[Callable[[SchemaT], None]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> SchemaT:
        last_error: Optional[Exception] = None
        for attempt in range(self._max_attempts):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        response_json_schema=response_schema or _gemini_json_schema(schema),
                    ),
                )
                text = getattr(response, "text", None)
                if not isinstance(text, str) or not text.strip():
                    raise ExternalServiceError(
                        ErrorType.MALFORMED_RESPONSE,
                        "Gemini returned no structured text",
                        retryable=True,
                    )
                parsed = schema.model_validate_json(text)
                if validate is not None:
                    validate(parsed)
                return parsed
            except (ValidationError, AnalysisValidationError):
                last_error = ExternalServiceError(
                    ErrorType.MALFORMED_RESPONSE,
                    "Gemini structured output failed validation",
                    retryable=True,
                )
            except Exception as error:
                mapped = self._map_error(error)
                last_error = mapped
                if not mapped.retryable:
                    raise mapped from error

            if attempt + 1 < self._max_attempts:
                delay = min(self._retry_max, self._retry_base * (2 ** attempt))
                self._sleep(delay * (0.5 + self._random()))

        if isinstance(last_error, ExternalServiceError):
            raise last_error
        raise ExternalServiceError(ErrorType.UNKNOWN_ERROR, "Gemini request failed")

    @staticmethod
    def _map_error(error: Exception) -> ExternalServiceError:
        if isinstance(error, ExternalServiceError):
            return error
        if isinstance(error, (httpx.TimeoutException, TimeoutError)):
            return ExternalServiceError(ErrorType.TIMEOUT, "Gemini request timed out", retryable=True)
        if isinstance(error, httpx.NetworkError):
            return ExternalServiceError(ErrorType.NETWORK_ERROR, "Gemini network error", retryable=True)
        status = getattr(error, "code", None)
        if status == 401:
            return ExternalServiceError(ErrorType.AUTHENTICATION_ERROR, "Gemini authentication failed")
        if status == 403:
            return ExternalServiceError(ErrorType.PERMISSION_ERROR, "Gemini permission denied")
        if status == 400:
            return ExternalServiceError(
                ErrorType.SCHEMA_CONFIGURATION_ERROR,
                "Gemini rejected the structured-output configuration",
            )
        if status == 429:
            return ExternalServiceError(ErrorType.RATE_LIMITED, "Gemini rate limit exceeded", retryable=True)
        if isinstance(status, int) and status >= 500:
            return ExternalServiceError(ErrorType.UPSTREAM_ERROR, "Gemini upstream error", retryable=True)
        return ExternalServiceError(ErrorType.UNKNOWN_ERROR, "Gemini request failed")
