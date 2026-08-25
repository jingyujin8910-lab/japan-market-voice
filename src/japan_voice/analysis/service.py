"""Structured analysis orchestration without a concrete external API client."""

from __future__ import annotations

from collections import Counter, defaultdict
import re
from typing import Dict, Iterable, List, Sequence, Tuple

from japan_voice.application.models import RunResult
from japan_voice.domain.enums import ContentGroup, Sentiment
from japan_voice.domain.records import ContentRecord
from .batching import split_record_batches
from .client import GeminiAnalysisClient
from .evidence import AnalysisValidationError, reconcile_aggregate_evidence
from .schemas import (
    AggregateAnalysis, AggregateStatus, AnalysisResult, EvidenceFinding,
    RecordAnalysis, SentimentSummary, TopicCount,
)
from japan_voice.infrastructure.errors import ExternalServiceError


class StructuredAnalysisService:
    _JAPANESE_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
    _FALLBACK_TERMS = {
        "航続距離": "주행거리", "充電インフラ": "충전 인프라", "充電設備": "충전 시설",
        "車中泊": "차박 활용성", "軽自動車": "경차", "商用車": "상용차",
        "電気自動車": "전기차", "補助金": "보조금", "車両価格": "차량 가격",
        "価格": "가격", "デザイン": "디자인", "荷室": "적재공간", "積載性": "적재성",
        "使い勝手": "사용 편의성", "販売店": "판매점", "ディーラー": "딜러",
        "アフターサービス": "사후 서비스", "リセールバリュー": "중고차 잔존가치",
        "ブランド": "브랜드", "信頼性": "신뢰성", "安全性": "안전성",
        "バッテリー": "배터리", "修理費": "수리비", "購入意向": "구매 의향",
        "購入": "구매", "充電": "충전", "走行距離": "주행거리", "サイズ": "크기",
        "室内空間": "실내 공간", "乗り心地": "승차감", "品質": "품질",
    }
    _POSITIVE_SIGNALS = (
        "良い", "いい", "好き", "欲しい", "最高", "素晴らしい", "期待",
        "便利", "かっこいい", "楽しみ", "買いたい", "気に入", "魅力",
        "good", "great", "love", "want", "excellent", "nice", "best",
        "좋", "최고", "마음에", "사고 싶", "기대", "멋지", "편리",
    )
    _NEGATIVE_SIGNALS = (
        "悪い", "高い", "不安", "問題", "残念", "いらない", "無理",
        "心配", "狭い", "遅い", "足りない", "難しい", "嫌い", "微妙",
        "bad", "expensive", "problem", "worry", "disappoint", "poor", "hate",
        "비싸", "문제", "걱정", "불안", "아쉽", "별로", "싫", "부족",
    )
    _TOPIC_SIGNALS = (
        (("価格", "値段", "price", "비싸", "가격"), "가격"),
        (("充電", "charger", "charging", "충전"), "충전 인프라"),
        (("航続", "走行距離", "range", "주행거리"), "주행거리"),
        (("デザイン", "design", "디자인", "かっこいい"), "디자인"),
        (("サイズ", "大きい", "小さい", "크기", "size"), "차량 크기"),
        (("室内", "車内", "공간", "space"), "실내 공간"),
        (("荷室", "積載", "cargo", "적재"), "적재공간"),
        (("発売", "販売", "launch", "출시"), "일본 출시"),
        (("ディーラー", "販売店", "dealer", "딜러"), "판매·딜러"),
        (("バッテリー", "battery", "배터리"), "배터리"),
        (("安全", "safety", "안전"), "안전성"),
        (("品質", "quality", "품질"), "품질"),
    )
    def __init__(
        self,
        client: GeminiAnalysisClient,
        *,
        batch_size: int = 30,
        batch_max_chars: int = 40_000,
    ) -> None:
        if batch_size <= 0 or batch_max_chars <= 0:
            raise ValueError("analysis batch limits must be positive")
        self._client = client
        self._batch_size = batch_size
        self._batch_max_chars = batch_max_chars

    def analyze(self, run: RunResult) -> AnalysisResult:
        records = list(run.eligible_records)
        by_id: Dict[str, ContentRecord] = {record.id: record for record in records}
        if len(by_id) != len(records):
            raise AnalysisValidationError("eligible record IDs must be unique")

        analyses: List[RecordAnalysis] = []
        for batch in split_record_batches(
            records,
            max_records=self._batch_size,
            max_chars=self._batch_max_chars,
        ):
            analyses.extend(self._analyze_resilient(batch))

        self._validate_record_analyses(analyses, by_id)
        sentiment = self._consumer_sentiment(analyses, by_id)
        aggregate_available = sentiment.consumer_voice_total > 0
        aggregate_status = (
            AggregateStatus.GEMINI if aggregate_available else AggregateStatus.NO_CONSUMER_DATA
        )
        aggregate_error_type = None
        invalid_evidence_ids_dropped = 0
        invalid_voc_dropped = 0
        try:
            aggregate = self._client.synthesize(records, analyses)
            aggregate, reconciliation = reconcile_aggregate_evidence(aggregate, records)
            aggregate = self.apply_majority_consistency(aggregate)
            invalid_evidence_ids_dropped = reconciliation.invalid_evidence_ids_dropped
            invalid_voc_dropped = reconciliation.invalid_voc_dropped
            if not self._usable_aggregate(aggregate) or not self._aggregate_is_korean(aggregate):
                aggregate_error_type = "no_data"
                aggregate, aggregate_status = self._fallback_aggregate(analyses, by_id, sentiment)
        except Exception as error:
            aggregate_error_type = (
                error.error_type if isinstance(error, ExternalServiceError)
                else "aggregate_validation_error"
            )
            aggregate, aggregate_status = self._fallback_aggregate(analyses, by_id, sentiment)
        aggregate_available = sentiment.consumer_voice_total > 0
        return AnalysisResult(
            record_analyses=analyses,
            sentiment=sentiment,
            aggregate=aggregate,
            aggregate_available=aggregate_available,
            aggregate_status=aggregate_status,
            aggregate_error_type=aggregate_error_type,
            invalid_evidence_ids_dropped=invalid_evidence_ids_dropped,
            invalid_voc_dropped=invalid_voc_dropped,
            analyzed_records=len(analyses),
            eligible_records=len(records),
        )

    def _analyze_resilient(
        self, records: Sequence[ContentRecord]
    ) -> List[RecordAnalysis]:
        """Keep successful work when one Gemini batch is too large or malformed.

        A failed batch is bisected so a single problematic/oversized record does
        not discard every other result.  At the singleton boundary we return an
        explicit UNKNOWN analysis; downstream summaries already exclude unknown
        sentiment, while the raw record remains visible to the user.
        """
        if not records:
            return []
        try:
            output = self._client.analyze_records(records)
        except Exception:
            if len(records) == 1:
                return [self._fallback_record_analysis(records[0])]
            middle = len(records) // 2
            return (
                self._analyze_resilient(records[:middle])
                + self._analyze_resilient(records[middle:])
            )
        expected = {record.id for record in records}
        actual = {item.record_id for item in output.analyses}
        if actual != expected:
            raise AnalysisValidationError(
                "record analysis IDs do not match requested batch"
            )
        output_by_id = {item.record_id: item for item in output.analyses}
        return [
            self._usable_record_analysis(output_by_id[record.id], record)
            for record in records
        ]

    @classmethod
    def _usable_record_analysis(
        cls, analysis: RecordAnalysis, record: ContentRecord
    ) -> RecordAnalysis:
        if record.content_group is ContentGroup.MARKET_CONTENT:
            if analysis.sentiment is Sentiment.UNKNOWN and analysis.sentiment_score is None:
                return analysis
            return RecordAnalysis(record_id=record.id, topics=analysis.topics)
        if analysis.sentiment is Sentiment.UNKNOWN:
            fallback = cls._fallback_record_analysis(record)
            # Retain a valid Gemini translation even when its sentiment was unknown.
            if analysis.translated_ko.strip():
                fallback = fallback.model_copy(
                    update={"translated_ko": analysis.translated_ko}
                )
            return fallback
        return analysis

    @classmethod
    def _fallback_record_analysis(cls, record: ContentRecord) -> RecordAnalysis:
        """Deterministic minimum analysis when Gemini cannot analyze one record."""
        if record.content_group is not ContentGroup.CONSUMER_VOICE:
            return RecordAnalysis(record_id=record.id)
        text = f"{record.title or ''} {record.content}".casefold()
        positive = sum(signal.casefold() in text for signal in cls._POSITIVE_SIGNALS)
        negative = sum(signal.casefold() in text for signal in cls._NEGATIVE_SIGNALS)
        if positive > negative:
            sentiment, score = Sentiment.POSITIVE, min(1.0, 0.35 + positive * 0.15)
        elif negative > positive:
            sentiment, score = Sentiment.NEGATIVE, max(-1.0, -0.35 - negative * 0.15)
        else:
            sentiment, score = Sentiment.NEUTRAL, 0.0
        topics = [
            label for signals, label in cls._TOPIC_SIGNALS
            if any(signal.casefold() in text for signal in signals)
        ][:10] or ["기타 소비자 반응"]
        question = "제품 관련 문의" if "?" in text or "？" in text else None
        wants_purchase = any(
            signal.casefold() in text
            for signal in ("欲しい", "買いたい", "購入", "want", "buy", "사고 싶", "구매")
        )
        return RecordAnalysis(
            record_id=record.id,
            sentiment=sentiment,
            sentiment_score=score,
            topics=topics,
            positive_drivers=topics[:3] if sentiment is Sentiment.POSITIVE else [],
            negative_drivers=topics[:3] if sentiment is Sentiment.NEGATIVE else [],
            customer_questions=[question] if question else [],
            purchase_signals=["구매 관심"] if wants_purchase and sentiment is not Sentiment.NEGATIVE else [],
            purchase_barriers=topics[:3] if sentiment is Sentiment.NEGATIVE else [],
            # Keep the original visible instead of presenting an invented translation.
            translated_ko=record.content[:2000],
        )

    @staticmethod
    def _finding_concept(text: str) -> str:
        value = re.sub(r"[^0-9a-zA-Z가-힣]", "", text).casefold()
        aliases = {
            "충전인프라": ("충전", "인프라", "충전소"),
            "가격": ("가격", "비용", "보조금"),
            "주행거리": ("주행거리", "항속거리"),
            "차량크기": ("차량크기", "차체크기", "사이즈"),
        }
        for concept, tokens in aliases.items():
            if any(token in value for token in tokens):
                return concept
        return value

    @classmethod
    def apply_majority_consistency(cls, aggregate: AggregateAnalysis) -> AggregateAnalysis:
        """Merge purchase barriers into concerns and reconcile opposing evidence."""
        concerns: List[EvidenceFinding] = []
        concern_indexes: Dict[str, int] = {}
        for finding in aggregate.negative_drivers + aggregate.purchase_barriers:
            concept = cls._finding_concept(finding.text)
            if concept in concern_indexes:
                index = concern_indexes[concept]
                existing = concerns[index]
                evidence_ids = list(dict.fromkeys(
                    existing.evidence_record_ids + finding.evidence_record_ids
                ))[:20]
                concerns[index] = existing.model_copy(
                    update={"evidence_record_ids": evidence_ids}
                )
                continue
            concern_indexes[concept] = len(concerns)
            concerns.append(finding)

        opposing: Dict[str, set[str]] = defaultdict(set)
        for finding in concerns:
            opposing[cls._finding_concept(finding.text)].update(finding.evidence_record_ids)
        positives = []
        for finding in aggregate.positive_drivers:
            positive_count = len(set(finding.evidence_record_ids))
            if len(opposing[cls._finding_concept(finding.text)]) > positive_count:
                continue
            positives.append(finding)
        return aggregate.model_copy(update={
            "positive_drivers": positives,
            "negative_drivers": concerns[:10],
            "purchase_barriers": [],
            "emerging_issues": [],
        })

    @staticmethod
    def _usable_aggregate(aggregate: AggregateAnalysis) -> bool:
        return any((
            aggregate.overall_voice,
            aggregate.positive_drivers,
            aggregate.negative_drivers,
            aggregate.marketing_insights,
        ))

    @classmethod
    def _aggregate_is_korean(cls, aggregate: AggregateAnalysis) -> bool:
        values = [item.text for name in (
            "overall_voice", "positive_drivers", "negative_drivers", "customer_questions",
            "purchase_signals", "purchase_barriers", "marketing_insights", "emerging_issues",
        ) for item in getattr(aggregate, name)]
        values.extend(item.topic for item in aggregate.top_topics)
        values.extend(item.korean_summary for item in aggregate.representative_voc)
        return not any(cls._JAPANESE_SCRIPT.search(value) for value in values)

    @classmethod
    def _normalize_fallback_term(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        for japanese, korean in sorted(cls._FALLBACK_TERMS.items(), key=lambda item: len(item[0]), reverse=True):
            normalized = normalized.replace(japanese, korean)
        # Unknown Japanese analysis labels are not exposed or guessed. They are
        # omitted so the safe data-insufficiency copy can be used instead.
        return "" if cls._JAPANESE_SCRIPT.search(normalized) else normalized

    @classmethod
    def _ranked(cls, values: Iterable[Tuple[str, str]], limit: int = 5) -> List[Tuple[str, int, List[str]]]:
        counts: Counter[str] = Counter()
        labels: Dict[str, str] = {}
        evidence: Dict[str, List[str]] = defaultdict(list)
        for value, record_id in values:
            cleaned = cls._normalize_fallback_term(value)
            if not cleaned:
                continue
            key = cleaned.casefold()
            counts[key] += 1
            labels.setdefault(key, cleaned)
            if record_id not in evidence[key]:
                evidence[key].append(record_id)
        return [
            (labels[key], count, evidence[key][:20])
            for key, count in counts.most_common(limit)
        ]

    @classmethod
    def _fallback_aggregate(
        cls,
        analyses: Sequence[RecordAnalysis],
        by_id: Dict[str, ContentRecord],
        sentiment: SentimentSummary,
    ) -> Tuple[AggregateAnalysis, AggregateStatus]:
        if sentiment.consumer_voice_total == 0:
            return AggregateAnalysis(), AggregateStatus.NO_CONSUMER_DATA
        consumer = [
            item for item in analyses
            if by_id[item.record_id].content_group is ContentGroup.CONSUMER_VOICE
            and item.sentiment is not Sentiment.UNKNOWN
        ]
        topics = cls._ranked(
            ((value, item.record_id) for item in consumer for value in item.topics), 10
        )
        positives = cls._ranked((value, item.record_id) for item in consumer for value in item.positive_drivers)
        negatives = cls._ranked(
            (value, item.record_id)
            for item in consumer
            for value in item.negative_drivers + item.purchase_barriers
        )
        barriers = cls._ranked((value, item.record_id) for item in consumer for value in item.purchase_barriers)
        questions = cls._ranked((value, item.record_id) for item in consumer for value in item.customer_questions)
        signals = cls._ranked((value, item.record_id) for item in consumer for value in item.purchase_signals)
        total = sentiment.consumer_voice_total
        percentages = {
            "긍정": round(sentiment.positive * 100 / total),
            "중립": round(sentiment.neutral * 100 / total),
            "부정": round(sentiment.negative * 100 / total),
        }
        leading = max(
            (("긍정", sentiment.positive), ("중립", sentiment.neutral), ("부정", sentiment.negative)),
            key=lambda pair: pair[1],
        )[0]
        detail_parts = []
        if topics: detail_parts.append(f"주요 관심사는 {topics[0][0]}입니다")
        if positives: detail_parts.append(f"긍정 평가 요인은 {positives[0][0]}입니다")
        if negatives: detail_parts.append(f"핵심 우려는 {negatives[0][0]}입니다")
        detail_text = " ".join(detail_parts)
        overall = (
            f"총 {total}개의 Consumer Voice가 분석되었습니다. "
            f"긍정 {percentages['긍정']}%, 중립 {percentages['중립']}%, "
            f"부정 {percentages['부정']}%이며 {leading} 반응의 비중이 가장 높습니다."
            + (f" {detail_text}" if detail_text else "")
        )
        consumer_ids = [item.record_id for item in consumer][:20]

        def findings(values, empty, template):
            return [EvidenceFinding(text=template.format(term=text), evidence_record_ids=ids) for text, _, ids in values] or [
                EvidenceFinding(text=empty, evidence_record_ids=[])
            ]

        marketing = cls._safe_marketing_insights(topics, negatives, barriers)
        has_detail = bool(topics or positives or negatives or barriers or questions or signals)
        aggregate = AggregateAnalysis(
            overall_voice=[EvidenceFinding(text=overall, evidence_record_ids=consumer_ids)],
            top_topics=[TopicCount(topic=text, count=count, evidence_record_ids=ids) for text, count, ids in topics],
            positive_drivers=findings(positives, "명확한 긍정 요인을 식별하기에 데이터가 부족합니다.",
                "주요 강점: {term}."),
            negative_drivers=findings(negatives, "명확한 부정 요인을 식별하기에 데이터가 부족합니다.",
                "주요 우려: {term}."),
            customer_questions=findings(questions, "반복 질문을 식별하기에 데이터가 부족합니다.",
                "반복적으로 확인된 질문: {term}."),
            purchase_signals=findings(signals, "명확한 구매 신호를 식별하기에 데이터가 부족합니다.",
                "구매 관심 신호로 {term} 관련 반응이 확인됩니다."),
            marketing_insights=marketing,
        )
        aggregate = cls.apply_majority_consistency(aggregate)
        return aggregate, (
            AggregateStatus.DETERMINISTIC_FALLBACK if has_detail
            else AggregateStatus.MINIMUM_FALLBACK
        )

    @staticmethod
    def _safe_marketing_insights(topics, negatives, barriers) -> List[EvidenceFinding]:
        rules = (
            (("가격", "price", "비용"), "가격 부담이 주요 관심 요인으로 확인됩니다. 판매가격만 제시하기보다 보조금 적용 가능성과 유지비를 포함한 가치 정보를 명확히 전달할 필요가 있습니다."),
            (("충전", "인프라", "charging"), "충전 편의성에 대한 우려가 확인됩니다. 일본 내 실제 충전 과정과 충전 시간, 주요 이동 상황을 구체적으로 보여주는 콘텐츠가 필요합니다."),
            (("주행거리", "range", "항속"), "실사용 주행거리에 대한 관심이 확인됩니다. 일본의 계절과 이용 상황별 주행거리 정보를 구체적으로 제공할 필요가 있습니다."),
            (("크기", "사이즈", "size"), "차량 크기가 이용 편의성 판단에 영향을 주고 있습니다. 일본 도로와 주차 환경에서의 실제 활용 장면을 제시할 필요가 있습니다."),
        )
        candidates = list(topics) + list(negatives) + list(barriers)
        output: List[EvidenceFinding] = []
        used = set()
        for label, _, ids in candidates:
            folded = label.casefold()
            for signals, message in rules:
                if any(signal in folded for signal in signals) and message not in used:
                    output.append(EvidenceFinding(text=message, evidence_record_ids=ids))
                    used.add(message)
        return output or [EvidenceFinding(text="추가 정성 분석이 필요합니다.", evidence_record_ids=[])]

    @staticmethod
    def _validate_record_analyses(
        analyses: List[RecordAnalysis],
        by_id: Dict[str, ContentRecord],
    ) -> None:
        ids = [analysis.record_id for analysis in analyses]
        if len(ids) != len(set(ids)) or set(ids) != set(by_id):
            raise AnalysisValidationError("record analyses must map one-to-one to eligible records")
        for analysis in analyses:
            record = by_id[analysis.record_id]
            if record.content_group is ContentGroup.MARKET_CONTENT:
                if analysis.sentiment is not Sentiment.UNKNOWN or analysis.sentiment_score is not None:
                    raise AnalysisValidationError("market content sentiment must remain unknown")

    @staticmethod
    def _consumer_sentiment(
        analyses: List[RecordAnalysis],
        by_id: Dict[str, ContentRecord],
    ) -> SentimentSummary:
        values = [
            analysis.sentiment
            for analysis in analyses
            if by_id[analysis.record_id].content_group is ContentGroup.CONSUMER_VOICE
        ]
        counts = Counter(values)
        positive = counts[Sentiment.POSITIVE]
        neutral = counts[Sentiment.NEUTRAL]
        negative = counts[Sentiment.NEGATIVE]
        unknown = counts[Sentiment.UNKNOWN]
        return SentimentSummary(
            positive=positive,
            neutral=neutral,
            negative=negative,
            unknown=unknown,
            consumer_voice_total=positive + neutral + negative,
            consumer_records_total=len(values),
            known_sentiment_total=positive + neutral + negative,
        )
