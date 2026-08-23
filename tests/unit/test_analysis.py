from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from japan_voice.analysis.batching import split_record_batches
from japan_voice.analysis.client import MockGeminiClient
from japan_voice.analysis.evidence import AnalysisValidationError
from japan_voice.analysis.schemas import AggregateAnalysis, AggregateStatus, EvidenceFinding, RecordAnalysis
from japan_voice.analysis.service import StructuredAnalysisService
from japan_voice.application.collection_service import CollectionRunResult
from japan_voice.application.pipeline import ProcessingPipeline
from japan_voice.collectors.base import CollectorResult
from japan_voice.domain.enums import ContentType, Sentiment, Source
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest


def content_record(
    record_id: str,
    *,
    content_type: ContentType,
    content: str,
    parent_id: str = "",
) -> ContentRecord:
    return ContentRecord(
        id=record_id,
        source=Source.YOUTUBE,
        provider="fixture",
        content_type=content_type,
        keyword="PV5",
        parent_id=parent_id or None,
        title="Kia PV5 日本発売",
        content=content,
        published_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        url=f"https://example.com/{record_id}",
        parent_url="https://example.com/video" if parent_id else None,
        is_comment=content_type is ContentType.COMMENT,
    )


def analyzed_run():
    request = SearchRequest(
        keyword="PV5",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 15),
        selected_sources=[Source.YOUTUBE],
        max_results=10,
    )
    records = [
        content_record(
            "video", content_type=ContentType.VIDEO,
            content="日本市場向けにPV5を発売するニュース",
        ),
        content_record(
            "positive", content_type=ContentType.COMMENT,
            content="デザインが好き。日本でも欲しい", parent_id="video",
        ),
        content_record(
            "negative", content_type=ContentType.COMMENT,
            content="価格が高いので購入を迷う", parent_id="video",
        ),
    ]
    collection = CollectionRunResult(
        results=[CollectorResult.success(Source.YOUTUBE, records)]
    )
    return ProcessingPipeline().process(collection, request, run_id="analysis-run")


def aggregate_payload(**overrides):
    payload = {
        "overall_voice": [
            {"text": "디자인 관심과 가격 우려가 함께 나타남", "evidence_record_ids": ["positive", "negative"]}
        ],
        "top_topics": [
            {"topic": "가격", "count": 1, "evidence_record_ids": ["negative"]},
            {"topic": "디자인", "count": 1, "evidence_record_ids": ["positive"]},
        ],
        "positive_drivers": [
            {"text": "디자인 선호", "evidence_record_ids": ["positive"]}
        ],
        "negative_drivers": [
            {"text": "높은 가격", "evidence_record_ids": ["negative"]}
        ],
        "customer_questions": [
            {"text": "일본 출시 시점", "evidence_record_ids": ["positive"]}
        ],
        "purchase_signals": [
            {"text": "구매 희망", "evidence_record_ids": ["positive"]}
        ],
        "purchase_barriers": [
            {"text": "가격 부담", "evidence_record_ids": ["negative"]}
        ],
        "representative_voc": [
            {
                "record_id": "positive",
                "quote": "日本でも欲しい",
                "korean_summary": "일본에서도 사고 싶다",
                "source": "youtube",
            }
        ],
        "marketing_insights": [
            {"text": "가격 정보를 명확히 제공", "evidence_record_ids": ["negative"]}
        ],
        "emerging_issues": [],
    }
    payload.update(overrides)
    return payload


def batch_outputs():
    return [
        {
            "analyses": [
                {
                    "record_id": "video",
                    "sentiment": "unknown",
                    "topics": ["일본 출시"],
                },
                {
                    "record_id": "positive",
                    "sentiment": "positive",
                    "sentiment_score": 0.8,
                    "topics": ["디자인", "구매 의향"],
                    "positive_drivers": ["디자인"],
                    "purchase_signals": ["欲しい"],
                },
            ]
        },
        {
            "analyses": [
                {
                    "record_id": "negative",
                    "sentiment": "negative",
                    "sentiment_score": -0.7,
                    "topics": ["가격"],
                    "negative_drivers": ["가격"],
                    "purchase_barriers": ["높은 가격"],
                }
            ]
        },
    ]


def test_batching_respects_record_and_character_limits() -> None:
    records = analyzed_run().eligible_records
    batches = split_record_batches(records, max_records=2, max_chars=10_000)
    assert [len(batch) for batch in batches] == [2, 1]
    char_batches = split_record_batches(records, max_records=10, max_chars=30)
    assert len(char_batches) >= 2
    with pytest.raises(ValueError):
        split_record_batches(records, max_records=0, max_chars=100)


def test_mock_structured_analysis_covers_required_outputs() -> None:
    run = analyzed_run()
    client = MockGeminiClient(
        batch_outputs=batch_outputs(),
        aggregate_output=aggregate_payload(),
    )
    result = StructuredAnalysisService(client, batch_size=2).analyze(run)

    assert result.analyzed_records == result.eligible_records == 3
    assert result.sentiment.model_dump() == {
        "positive": 1,
        "neutral": 0,
        "negative": 1,
        "unknown": 0,
        "consumer_voice_total": 2,
        "consumer_records_total": 2,
        "known_sentiment_total": 2,
    }
    assert result.aggregate.top_topics[0].topic == "가격"
    assert result.aggregate.positive_drivers
    assert result.aggregate.negative_drivers
    assert result.aggregate.customer_questions
    assert result.aggregate.purchase_signals
    assert result.aggregate.purchase_barriers == []
    assert any("가격" in item.text for item in result.aggregate.negative_drivers)
    assert result.aggregate.representative_voc[0].record_id == "positive"
    assert result.aggregate.marketing_insights
    assert client.analyze_calls == 2
    assert client.synthesize_calls == 1


def test_market_content_sentiment_cannot_pollute_consumer_summary() -> None:
    outputs = batch_outputs()
    outputs[0]["analyses"][0] = {
        "record_id": "video",
        "sentiment": "positive",
        "sentiment_score": 0.9,
        "topics": ["일본 출시"],
    }
    client = MockGeminiClient(batch_outputs=outputs, aggregate_output=aggregate_payload())
    with pytest.raises(AnalysisValidationError, match="market content sentiment"):
        StructuredAnalysisService(client, batch_size=2).analyze(analyzed_run())


def test_unknown_or_missing_record_analysis_ids_are_rejected() -> None:
    outputs = batch_outputs()
    outputs[0]["analyses"][0]["record_id"] = "invented"
    client = MockGeminiClient(batch_outputs=outputs, aggregate_output=aggregate_payload())
    with pytest.raises(AnalysisValidationError, match="requested batch"):
        StructuredAnalysisService(client, batch_size=2).analyze(analyzed_run())


def test_unknown_insight_evidence_id_is_removed_without_losing_finding() -> None:
    aggregate = aggregate_payload(
        marketing_insights=[
            {"text": "근거 없는 제안", "evidence_record_ids": ["invented"]}
        ]
    )
    client = MockGeminiClient(batch_outputs=batch_outputs(), aggregate_output=aggregate)
    result = StructuredAnalysisService(client, batch_size=2).analyze(analyzed_run())
    assert result.aggregate.marketing_insights[0].text == "근거 없는 제안"
    assert result.aggregate.marketing_insights[0].evidence_record_ids == []
    assert result.invalid_evidence_ids_dropped == 1


def test_consumer_findings_drop_market_content_evidence() -> None:
    aggregate = aggregate_payload(
        positive_drivers=[
            {"text": "기사의 긍정 논조", "evidence_record_ids": ["video"]}
        ]
    )
    client = MockGeminiClient(batch_outputs=batch_outputs(), aggregate_output=aggregate)
    result = StructuredAnalysisService(client, batch_size=2).analyze(analyzed_run())
    assert result.aggregate.positive_drivers[0].evidence_record_ids == []
    assert result.invalid_evidence_ids_dropped == 1


@pytest.mark.parametrize(
    "voc",
    [
        {
            "record_id": "invented",
            "quote": "존재하지 않는 인용",
            "korean_summary": "가짜",
            "source": "youtube",
        },
        {
            "record_id": "positive",
            "quote": "원문에 없는 문장",
            "korean_summary": "가짜",
            "source": "youtube",
        },
        {
            "record_id": "positive",
            "quote": "日本でも欲しい",
            "korean_summary": "출처 불일치",
            "source": "news",
        },
    ],
)
def test_invalid_representative_voc_is_removed(voc: dict) -> None:
    client = MockGeminiClient(
        batch_outputs=batch_outputs(),
        aggregate_output=aggregate_payload(representative_voc=[voc]),
    )
    result = StructuredAnalysisService(client, batch_size=2).analyze(analyzed_run())
    assert result.aggregate.representative_voc == []
    assert result.invalid_voc_dropped == 1


def test_empty_gemini_aggregate_uses_deterministic_fallback() -> None:
    client = MockGeminiClient(batch_outputs=batch_outputs(), aggregate_output={})
    result = StructuredAnalysisService(client, batch_size=2).analyze(analyzed_run())
    assert result.aggregate_available is True
    assert result.aggregate_status is AggregateStatus.DETERMINISTIC_FALLBACK
    assert result.aggregate.overall_voice
    assert result.aggregate.positive_drivers
    assert result.aggregate.negative_drivers
    assert result.aggregate.purchase_barriers == []
    assert result.aggregate.marketing_insights
    assert result.aggregate.emerging_issues == []


def test_sparse_record_analysis_uses_minimum_safe_summary() -> None:
    sparse = batch_outputs()
    for batch in sparse:
        for item in batch["analyses"]:
            item.pop("topics", None)
            item.pop("positive_drivers", None)
            item.pop("negative_drivers", None)
            item.pop("purchase_signals", None)
            item.pop("purchase_barriers", None)
    client = MockGeminiClient(batch_outputs=sparse, aggregate_output={})
    result = StructuredAnalysisService(client, batch_size=2).analyze(analyzed_run())
    assert result.sentiment.consumer_voice_total == 2
    assert result.aggregate_available is True
    assert result.aggregate_status is AggregateStatus.MINIMUM_FALLBACK
    assert "총 2개의 Consumer Voice" in result.aggregate.overall_voice[0].text
    assert all((result.aggregate.positive_drivers, result.aggregate.negative_drivers,
        result.aggregate.marketing_insights))
    assert result.aggregate.purchase_barriers == []
    assert result.aggregate.emerging_issues == []


def test_japanese_gemini_aggregate_is_replaced_by_korean_fallback() -> None:
    japanese = aggregate_payload(
        overall_voice=[{"text":"価格と充電インフラが主な関心事です", "evidence_record_ids":["negative"]}]
    )
    client = MockGeminiClient(batch_outputs=batch_outputs(), aggregate_output=japanese)
    result = StructuredAnalysisService(client, batch_size=2).analyze(analyzed_run())
    assert result.aggregate_status is AggregateStatus.DETERMINISTIC_FALLBACK
    human_text = " ".join(
        item.text for field in (result.aggregate.overall_voice, result.aggregate.positive_drivers,
            result.aggregate.negative_drivers, result.aggregate.purchase_barriers,
            result.aggregate.marketing_insights, result.aggregate.emerging_issues) for item in field
    )
    assert not StructuredAnalysisService._JAPANESE_SCRIPT.search(human_text)


def test_fallback_normalizes_japanese_automotive_terms_without_touching_records() -> None:
    outputs = batch_outputs()
    outputs[0]["analyses"][1]["topics"] = ["充電インフラ", "車中泊"]
    outputs[1]["analyses"][0]["negative_drivers"] = ["航続距離", "車両価格"]
    original = analyzed_run().consumer_voice_records[0].content
    result = StructuredAnalysisService(
        MockGeminiClient(batch_outputs=outputs, aggregate_output={}), batch_size=2
    ).analyze(analyzed_run())
    rendered = " ".join(item.topic for item in result.aggregate.top_topics)
    rendered += " " + " ".join(item.text for item in result.aggregate.negative_drivers)
    assert "충전 인프라" in rendered and "차박 활용성" in rendered
    assert "주행거리" in rendered and "차량 가격" in rendered
    assert analyzed_run().consumer_voice_records[0].content == original


def test_pydantic_rejects_invalid_sentiment_shape() -> None:
    with pytest.raises(ValidationError):
        RecordAnalysis(
            record_id="record",
            sentiment=Sentiment.UNKNOWN,
            sentiment_score=0.5,
        )
    with pytest.raises(ValidationError):
        RecordAnalysis(record_id="record", sentiment="happy")


def test_majority_consistency_removes_positive_minority_for_same_concept() -> None:
    aggregate = AggregateAnalysis(
        positive_drivers=[EvidenceFinding(text="충전 인프라가 잘 갖춰져 있음", evidence_record_ids=["p1"])],
        negative_drivers=[EvidenceFinding(text="충전소 부족", evidence_record_ids=["n1", "n2"])],
        purchase_barriers=[EvidenceFinding(text="충전 인프라 우려", evidence_record_ids=["n2"])],
    )
    reconciled = StructuredAnalysisService.apply_majority_consistency(aggregate)
    assert reconciled.positive_drivers == []
    assert len(reconciled.negative_drivers) == 1
    assert reconciled.negative_drivers[0].evidence_record_ids == ["n1", "n2"]
    assert reconciled.purchase_barriers == []
