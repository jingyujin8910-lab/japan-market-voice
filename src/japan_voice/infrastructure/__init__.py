"""Shared external-communication infrastructure."""

from .errors import ErrorType, ExternalServiceError
from .http import HttpClient, HttpClientConfig
from .logging import StructuredLogger

__all__ = ["ErrorType", "ExternalServiceError", "HttpClient", "HttpClientConfig", "StructuredLogger"]

