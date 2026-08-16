"""Meaning-preserving text and URL normalization."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_TRACKING_KEYS = {"fbclid", "gclid", "yclid", "ref", "source"}


def normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = _HTML_TAG.sub(" ", value)
    value = unicodedata.normalize("NFKC", value)
    return _WHITESPACE.sub(" ", value).strip()


def normalize_for_match(value: str) -> str:
    return normalize_text(value).casefold()


def canonicalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()
    port = parts.port
    netloc = hostname
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{hostname}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path) or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
        )
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def normalized_text_hash(value: str) -> str:
    return hashlib.sha256(normalize_for_match(value).encode("utf-8")).hexdigest()

