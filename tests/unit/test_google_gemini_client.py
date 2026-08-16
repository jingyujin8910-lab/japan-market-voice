import json
from types import SimpleNamespace

import pytest

from japan_voice.analysis.google_client import GoogleGeminiClient, _gemini_json_schema
from japan_voice.analysis.schemas import RecordAnalysis
from japan_voice.domain.enums import ContentGroup, ContentType, EntityMatch, Source
from japan_voice.domain.records import ContentRecord
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError


def record(record_id: str = "comment") -> ContentRecord:
    return ContentRecord(
        id=record_id,
        source=Source.YOUTUBE,
        provider="fixture",
        content_type=ContentType.COMMENT,
        content_group=ContentGroup.CONSUMER_VOICE,
        keyword="PV5",
        title="Kia PV5 日本発売",
        content="日本でも欲しい",
        url=f"https://example.com/{record_id}",
        is_comment=True,
    )


class CodedError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__("sensitive upstream error must not escape")
        self.code = code


class FakeModels:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(text=output if isinstance(output, str) else json.dumps(output))


class FakeSdkClient:
    def __init__(self, outputs):
        self.models = FakeModels(outputs)


def client(outputs, delays=None) -> GoogleGeminiClient:
    return GoogleGeminiClient(
        model="test-model",
        sdk_client=FakeSdkClient(outputs),
        max_attempts=2,
        retry_base_seconds=0.01,
        retry_max_seconds=0.02,
        sleep=(delays.append if delays is not None else lambda _: None),
        random_value=lambda: 0.5,
    )


def analysis_payload(record_id="comment"):
    return {
        "analyses": [
            {
                "record_id": record_id,
                "sentiment": "positive",
                "sentiment_score": 0.8,
                "topics": ["구매 의향"],
                "positive_drivers": ["일본 출시 기대"],
            }
        ]
    }


def test_adapter_connects_pydantic_schema_and_validates_ids() -> None:
    adapter = client([analysis_payload()])
    result = adapter.analyze_records([record()])
    assert result.analyses[0].record_id == "comment"
    call = adapter._client.models.calls[0]
    assert call["model"] == "test-model"
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_json_schema is not None


def test_wire_schema_recursively_removes_additional_properties_only() -> None:
    schema = _gemini_json_schema(type(client([analysis_payload()]).analyze_records([record()])))

    def contains_additional_properties(value):
        if isinstance(value, dict):
            return "additionalProperties" in value or any(
                contains_additional_properties(item) for item in value.values()
            )
        if isinstance(value, list):
            return any(contains_additional_properties(item) for item in value)
        return False

    assert contains_additional_properties(schema) is False


def test_scope_classification_schema_and_ids() -> None:
    adapter = client(
        [
            {
                "classifications": [
                    {
                        "record_id": "comment",
                        "entity_match": "target",
                        "japan_market_relevant": True,
                        "japan_market_score": 0.9,
                        "content_group": "consumer_voice",
                        "reason": "일본 출시를 요구하는 댓글",
                    }
                ]
            }
        ]
    )
    result = adapter.classify_scope([record()])
    assert result.classifications[0].entity_match is EntityMatch.TARGET


def test_validation_failure_retries_once_then_succeeds() -> None:
    delays = []
    adapter = client([{"wrong": []}, analysis_payload()], delays)
    result = adapter.analyze_records([record()])
    assert result.analyses[0].record_id == "comment"
    assert len(adapter._client.models.calls) == 2
    assert len(delays) == 1


def test_transient_error_retries_but_ordinary_4xx_does_not() -> None:
    adapter = client([CodedError(503), analysis_payload()])
    assert adapter.analyze_records([record()]).analyses
    assert len(adapter._client.models.calls) == 2

    adapter = client([CodedError(400), analysis_payload()])
    with pytest.raises(ExternalServiceError) as caught:
        adapter.analyze_records([record()])
    assert caught.value.code is ErrorType.SCHEMA_CONFIGURATION_ERROR
    assert len(adapter._client.models.calls) == 1
    assert "sensitive upstream" not in str(caught.value)


def test_429_is_bounded_to_two_total_attempts() -> None:
    adapter = client([CodedError(429), CodedError(429)])
    with pytest.raises(ExternalServiceError) as caught:
        adapter.analyze_records([record()])
    assert caught.value.code is ErrorType.RATE_LIMITED
    assert len(adapter._client.models.calls) == 2


def test_adapter_retries_then_rejects_invented_record_id() -> None:
    adapter = client([analysis_payload("invented"), analysis_payload("invented")])
    with pytest.raises(ExternalServiceError) as caught:
        adapter.analyze_records([record()])
    assert caught.value.code is ErrorType.MALFORMED_RESPONSE
    assert len(adapter._client.models.calls) == 2


def test_aggregate_evidence_is_reconciled_by_analysis_service() -> None:
    invalid = {
        "marketing_insights": [
            {"text": "근거 없는 제안", "evidence_record_ids": ["invented"]}
        ]
    }
    adapter = client([invalid])
    analysis = RecordAnalysis(
        record_id="comment",
        sentiment="positive",
        sentiment_score=0.8,
    )
    result = adapter.synthesize([record()], [analysis])
    assert result.marketing_insights[0].evidence_record_ids == ["invented"]
    assert len(adapter._client.models.calls) == 1


def test_empty_aggregate_is_retried_then_preserves_valid_content() -> None:
    valid = {
        "overall_voice": [
            {"text": "일본 시장 반응 요약", "evidence_record_ids": ["comment"]}
        ]
    }
    adapter = client([{}, valid])
    analysis = RecordAnalysis(
        record_id="comment", sentiment="positive", sentiment_score=0.8
    )
    result = adapter.synthesize([record()], [analysis])
    assert result.overall_voice[0].text == "일본 시장 반응 요약"
    assert len(adapter._client.models.calls) == 2
