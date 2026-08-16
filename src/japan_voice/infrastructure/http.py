"""Synchronous httpx client with bounded retry and safe error mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import email.utils
import random
import time
from typing import Any, Callable, Dict, Mapping, Optional

import httpx

from .errors import ErrorType, ExternalServiceError


@dataclass(frozen=True)
class HttpClientConfig:
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0
    overall_timeout_seconds: float = 20.0
    max_retries: int = 2
    backoff_base_seconds: float = 0.25
    backoff_max_seconds: float = 4.0

    def __post_init__(self) -> None:
        if min(
            self.connect_timeout_seconds,
            self.read_timeout_seconds,
            self.overall_timeout_seconds,
            self.backoff_base_seconds,
            self.backoff_max_seconds,
        ) <= 0:
            raise ValueError("HTTP timeout and backoff values must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")

    @classmethod
    def from_settings(cls, settings: Any) -> "HttpClientConfig":
        return cls(
            connect_timeout_seconds=settings.http_connect_timeout_seconds,
            read_timeout_seconds=settings.http_read_timeout_seconds,
            overall_timeout_seconds=settings.request_timeout_seconds,
            max_retries=settings.http_max_retries,
            backoff_base_seconds=settings.http_backoff_base_seconds,
            backoff_max_seconds=settings.http_backoff_max_seconds,
        )


def _google_error_reason(response: httpx.Response) -> Optional[str]:
    try:
        payload = response.json()
        errors = payload.get("error", {}).get("errors", [])
        return errors[0].get("reason") if errors else None
    except (ValueError, AttributeError, IndexError, TypeError):
        return None


def _http_error(response: httpx.Response) -> ExternalServiceError:
    status = response.status_code
    reason = _google_error_reason(response)
    details = {"reason": reason} if reason else {}
    if status == 401 or reason in {"keyInvalid", "authError"}:
        kind = ErrorType.AUTHENTICATION_ERROR
    elif status == 403 and reason in {
        "quotaExceeded", "dailyLimitExceeded", "dailyLimitExceededUnreg",
    }:
        kind = ErrorType.QUOTA_EXCEEDED
    elif status in {403, 429} and reason in {"rateLimitExceeded", "userRateLimitExceeded"}:
        kind = ErrorType.RATE_LIMITED
    elif status == 403:
        kind = ErrorType.PERMISSION_ERROR
    elif status == 429:
        kind = ErrorType.RATE_LIMITED
    elif status >= 500:
        kind = ErrorType.UPSTREAM_ERROR
    else:
        kind = ErrorType.UNKNOWN_ERROR
    return ExternalServiceError(
        kind,
        f"Upstream request failed with HTTP {status}",
        status_code=status,
        details=details,
        retryable=status == 429 or status >= 500,
    )


def _retry_after_seconds(value: Optional[str], now: Optional[datetime] = None) -> Optional[float]:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            parsed = email.utils.parsedate_to_datetime(value)
            current = now or datetime.now(timezone.utc)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0.0, (parsed - current).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class HttpClient:
    def __init__(
        self,
        config: HttpClientConfig,
        *,
        client: Optional[httpx.Client] = None,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._client = client or httpx.Client()
        self._owns_client = client is None
        self._sleep = sleep
        self._random = random_value
        self._monotonic = monotonic

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_json(
        self,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        started = self._monotonic()
        attempts = self.config.max_retries + 1
        last_error: Optional[ExternalServiceError] = None

        for attempt in range(attempts):
            elapsed = self._monotonic() - started
            remaining = self.config.overall_timeout_seconds - elapsed
            if remaining <= 0:
                raise ExternalServiceError(ErrorType.TIMEOUT, "Overall request timeout exceeded")
            timeout = httpx.Timeout(
                min(self.config.read_timeout_seconds, remaining),
                connect=min(self.config.connect_timeout_seconds, remaining),
            )
            response: Optional[httpx.Response] = None
            try:
                response = self._client.get(url, params=params, headers=headers, timeout=timeout)
                if response.status_code >= 400:
                    raise _http_error(response)
                try:
                    payload = response.json()
                except ValueError as error:
                    raise ExternalServiceError(
                        ErrorType.MALFORMED_RESPONSE,
                        "Upstream returned invalid JSON",
                    ) from error
                if not isinstance(payload, dict):
                    raise ExternalServiceError(
                        ErrorType.MALFORMED_RESPONSE,
                        "Upstream JSON must be an object",
                    )
                return payload
            except httpx.TimeoutException as error:
                last_error = ExternalServiceError(ErrorType.TIMEOUT, "Upstream request timed out", retryable=True)
            except httpx.NetworkError as error:
                last_error = ExternalServiceError(ErrorType.NETWORK_ERROR, "Upstream network error", retryable=True)
            except ExternalServiceError as error:
                last_error = error

            if last_error is None or not last_error.retryable or attempt == attempts - 1:
                raise last_error or ExternalServiceError(ErrorType.UNKNOWN_ERROR, "Unknown HTTP error")

            retry_after = _retry_after_seconds(response.headers.get("Retry-After")) if response else None
            exponential = min(
                self.config.backoff_max_seconds,
                self.config.backoff_base_seconds * (2 ** attempt),
            )
            delay = retry_after if retry_after is not None else exponential * (0.5 + self._random())
            remaining = self.config.overall_timeout_seconds - (self._monotonic() - started)
            if delay >= remaining:
                raise ExternalServiceError(ErrorType.TIMEOUT, "Overall request timeout exceeded")
            self._sleep(delay)

        raise last_error or ExternalServiceError(ErrorType.UNKNOWN_ERROR, "Unknown HTTP error")

    def get_text(
        self,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> str:
        """GET public text content with the same bounded safety policy."""
        started = self._monotonic()
        attempts = self.config.max_retries + 1
        last_error: Optional[ExternalServiceError] = None
        for attempt in range(attempts):
            remaining = self.config.overall_timeout_seconds - (self._monotonic() - started)
            if remaining <= 0:
                raise ExternalServiceError(ErrorType.TIMEOUT, "Overall request timeout exceeded")
            timeout = httpx.Timeout(
                min(self.config.read_timeout_seconds, remaining),
                connect=min(self.config.connect_timeout_seconds, remaining),
            )
            response: Optional[httpx.Response] = None
            try:
                response = self._client.get(url, params=params, headers=headers, timeout=timeout)
                if response.status_code >= 400:
                    raise _http_error(response)
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type and "text/plain" not in content_type:
                    raise ExternalServiceError(
                        ErrorType.MALFORMED_RESPONSE,
                        "Upstream returned an unsupported content type",
                    )
                return response.text
            except httpx.TimeoutException:
                last_error = ExternalServiceError(ErrorType.TIMEOUT, "Upstream request timed out", retryable=True)
            except httpx.NetworkError:
                last_error = ExternalServiceError(ErrorType.NETWORK_ERROR, "Upstream network error", retryable=True)
            except ExternalServiceError as error:
                last_error = error
            if last_error is None or not last_error.retryable or attempt == attempts - 1:
                raise last_error or ExternalServiceError(ErrorType.UNKNOWN_ERROR, "Unknown HTTP error")
            retry_after = _retry_after_seconds(response.headers.get("Retry-After")) if response else None
            exponential = min(self.config.backoff_max_seconds, self.config.backoff_base_seconds * (2 ** attempt))
            delay = retry_after if retry_after is not None else exponential * (0.5 + self._random())
            remaining = self.config.overall_timeout_seconds - (self._monotonic() - started)
            if delay >= remaining:
                raise ExternalServiceError(ErrorType.TIMEOUT, "Overall request timeout exceeded")
            self._sleep(delay)
        raise last_error or ExternalServiceError(ErrorType.UNKNOWN_ERROR, "Unknown HTTP error")
