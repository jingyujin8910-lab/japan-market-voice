#!/usr/bin/env python3
"""Minimal YouTube-to-Gemini structured-output smoke test."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from japan_voice.analysis.google_client import GoogleGeminiClient
from japan_voice.analysis.service import StructuredAnalysisService
from japan_voice.application.collection_service import CollectionRunResult
from japan_voice.application.models import AuditMetrics, RunResult
from japan_voice.application.pipeline import ProcessingPipeline
from japan_voice.application.query_planner import expand_japan_queries
from japan_voice.collectors.youtube import YouTubeCollector
from japan_voice.config.settings import get_secret, load_settings
from japan_voice.domain.enums import CollectorStatus, Source
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.errors import ExternalServiceError
from japan_voice.infrastructure.http import HttpClient, HttpClientConfig


def _output(
    *,
    success: bool,
    model: str,
    error_type: Optional[str] = None,
    analyzed_records: int = 0,
    sentiment: Optional[Dict[str, int]] = None,
    topics: int = 0,
    positive_drivers: int = 0,
    negative_drivers: int = 0,
    representative_voc_validated: bool = False,
    marketing_insights: int = 0,
) -> Dict[str, Any]:
    return {
        "structured_output_success": success,
        "model": model,
        "analyzed_records": analyzed_records,
        "sentiment": sentiment or {},
        "topics_count": topics,
        "positive_drivers_count": positive_drivers,
        "negative_drivers_count": negative_drivers,
        "representative_voc_validated": representative_voc_validated,
        "marketing_insights_count": marketing_insights,
        "error_type": error_type,
    }


def main() -> int:
    settings = load_settings(load_dotenv_file=True)
    youtube_key = get_secret("YOUTUBE_API_KEY")
    gemini_key = get_secret("GEMINI_API_KEY")
    if not youtube_key or not gemini_key:
        print(json.dumps(_output(
            success=False,
            model=settings.gemini_model,
            error_type="authentication_error",
        ), ensure_ascii=False))
        return 2

    smoke_settings = replace(
        settings,
        youtube_max_videos=1,
        youtube_comments_per_video=1,
        max_query_variants_per_source=1,
        gemini_batch_size=1,
    )
    today_jst = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    request = SearchRequest(
        keyword="PV5",
        start_date=today_jst - timedelta(days=365),
        end_date=today_jst,
        selected_sources=[Source.YOUTUBE],
        max_results=1,
    )
    planned = expand_japan_queries("PV5", Source.YOUTUBE, max_queries=3)
    queries = [next((query for query in planned if "日本発売" in query), planned[0])]
    http = HttpClient(HttpClientConfig.from_settings(smoke_settings))
    gemini: Optional[GoogleGeminiClient] = None
    try:
        collected = YouTubeCollector(
            http=http,
            settings=smoke_settings,
            api_key=youtube_key,
        ).collect(request, queries)
        if collected.status is CollectorStatus.FAILED:
            print(json.dumps(_output(
                success=False,
                model=smoke_settings.gemini_model,
                error_type=collected.error_type,
            ), ensure_ascii=False))
            return 1
        processed = ProcessingPipeline().process(
            CollectionRunResult(results=[collected]), request
        )
        consumer = processed.consumer_voice_records[:1]
        if not consumer:
            print(json.dumps(_output(
                success=False,
                model=smoke_settings.gemini_model,
                error_type="no_data",
            ), ensure_ascii=False))
            return 1

        mini_run = RunResult(
            run_id="gemini-smoke",
            request=request,
            collector_results=[collected],
            raw_records=consumer,
            eligible_records=consumer,
            consumer_voice_records=consumer,
            market_content_records=[],
            excluded_records=[],
            audit=AuditMetrics(
                raw_collected=1,
                entity_excluded=0,
                japan_scope_excluded=0,
                date_excluded=0,
                duplicates_removed=0,
                final_eligible=1,
                consumer_voice_count=1,
                market_content_count=0,
            ),
        )
        gemini = GoogleGeminiClient.from_settings(smoke_settings, api_key=gemini_key)
        result = StructuredAnalysisService(
            gemini,
            batch_size=1,
            batch_max_chars=4_000,
        ).analyze(mini_run)
        sentiment = {
            "positive": result.sentiment.positive,
            "neutral": result.sentiment.neutral,
            "negative": result.sentiment.negative,
            "unknown": result.sentiment.unknown,
        }
        print(json.dumps(_output(
            success=True,
            model=gemini.model,
            analyzed_records=result.analyzed_records,
            sentiment=sentiment,
            topics=len(result.aggregate.top_topics),
            positive_drivers=len(result.aggregate.positive_drivers),
            negative_drivers=len(result.aggregate.negative_drivers),
            representative_voc_validated=bool(result.aggregate.representative_voc),
            marketing_insights=len(result.aggregate.marketing_insights),
        ), ensure_ascii=False))
        return 0
    except ExternalServiceError as error:
        print(json.dumps(_output(
            success=False,
            model=settings.gemini_model,
            error_type=error.error_type,
        ), ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps(_output(
            success=False,
            model=settings.gemini_model,
            error_type="unknown_error",
        ), ensure_ascii=False))
        return 1
    finally:
        http.close()
        if gemini is not None:
            gemini.close()


if __name__ == "__main__":
    raise SystemExit(main())

