"""Safe, source-independent external error taxonomy."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Optional


class ErrorType(str, Enum):
    AUTHENTICATION_ERROR = "authentication_error"
    PERMISSION_ERROR = "permission_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    UPSTREAM_ERROR = "upstream_error"
    MALFORMED_RESPONSE = "malformed_response"
    SCHEMA_CONFIGURATION_ERROR = "schema_configuration_error"
    NO_DATA = "no_data"
    UNKNOWN_ERROR = "unknown_error"


class ExternalServiceError(Exception):
    def __init__(
        self,
        error_type: ErrorType,
        message: str,
        *,
        status_code: Optional[int] = None,
        details: Optional[Mapping[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = error_type
        self.error_type = error_type.value
        self.status_code = status_code
        self.details = dict(details or {})
        self.retryable = retryable
