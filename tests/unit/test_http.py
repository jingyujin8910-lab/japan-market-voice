import json
import logging

import httpx
import pytest

from japan_voice.domain.enums import Source
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError
from japan_voice.infrastructure.http import HttpClient, HttpClientConfig
from japan_voice.infrastructure.logging import StructuredLogger


def config(**overrides: object) -> HttpClientConfig:
    values = {
        "connect_timeout_seconds": 1,
        "read_timeout_seconds": 1,
        "overall_timeout_seconds": 10,
        "max_retries": 2,
        "backoff_base_seconds": 0.01,
        "backoff_max_seconds": 0.1,
    }
    values.update(overrides)
    return HttpClientConfig(**values)


def test_http_retries_429_and_respects_retry_after() -> None:
    calls = 0
    delays = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, json={"error": {}})
        return httpx.Response(200, json={"items": []})

    raw = httpx.Client(transport=httpx.MockTransport(handler))
    client = HttpClient(config(), client=raw, sleep=delays.append)
    assert client.get_json("https://example.test/data") == {"items": []}
    assert calls == 2
    assert delays == [2.0]


def test_http_does_not_retry_most_4xx() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": {"message": "bad"}})

    client = HttpClient(config(), client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ExternalServiceError) as caught:
        client.get_json("https://example.test/data")
    assert caught.value.code is ErrorType.UNKNOWN_ERROR
    assert calls == 1


def test_http_timeout_is_bounded_and_typed() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("secret-bearing raw error", request=request)

    client = HttpClient(
        config(max_retries=1),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )
    with pytest.raises(ExternalServiceError) as caught:
        client.get_json("https://example.test/data", params={"key": "do-not-log"})
    assert caught.value.code is ErrorType.TIMEOUT
    assert "secret-bearing" not in str(caught.value)
    assert calls == 2


def test_http_maps_youtube_quota_and_malformed_json() -> None:
    quota = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                403,
                json={"error": {"errors": [{"reason": "quotaExceeded"}]}},
            )
        )
    )
    with pytest.raises(ExternalServiceError) as caught:
        HttpClient(config(), client=quota).get_json("https://example.test/data")
    assert caught.value.code is ErrorType.QUOTA_EXCEEDED

    malformed = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="not-json")
        )
    )
    with pytest.raises(ExternalServiceError) as caught:
        HttpClient(config(), client=malformed).get_json("https://example.test/data")
    assert caught.value.code is ErrorType.MALFORMED_RESPONSE


def test_structured_logger_uses_allowlisted_fields(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("test-structured")
    caplog.set_level(logging.INFO, logger="test-structured")
    entry = StructuredLogger(logger).event(
        run_id="run-1",
        source=Source.YOUTUBE,
        event="collector_completed",
        duration_ms=12,
        records_collected=3,
        error_type=None,
        metric_api_calls=2,
        authorization="Bearer should-not-appear",
        api_key="should-not-appear",
        content="full comment should-not-appear",
    )
    parsed = json.loads(caplog.records[-1].message)
    assert parsed == entry
    assert parsed["metric_api_calls"] == 2
    assert "authorization" not in parsed
    assert "api_key" not in parsed
    assert "content" not in parsed
    assert "should-not-appear" not in caplog.records[-1].message

