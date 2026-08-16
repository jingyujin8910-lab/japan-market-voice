#!/usr/bin/env python3
"""Minimal, secret-free Yahoo Japan public-web smoke test."""

from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from japan_voice.application.collection_service import CollectionOrchestrator
from japan_voice.application.pipeline import ProcessingPipeline
from japan_voice.collectors.yahoo_japan import YahooJapanCollector
from japan_voice.config.settings import load_settings
from japan_voice.domain.enums import ContentGroup, Source, YahooSubSource
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.http import HttpClient, HttpClientConfig


def main() -> int:
    settings = replace(
        load_settings(load_dotenv_file=True), yahoo_max_queries=1,
        yahoo_news_articles_per_query=3, yahoo_comments_per_article=5,
        yahoo_questions_per_query=3, yahoo_answers_per_question=3,
    )
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    request = SearchRequest(keyword="PV5", start_date=today - timedelta(days=30),
        end_date=today, selected_sources=[Source.YAHOO_JAPAN], max_results=20)
    http = HttpClient(HttpClientConfig.from_settings(settings))
    try:
        collection = CollectionOrchestrator(
            [YahooJapanCollector(http=http, settings=settings)], max_queries_per_source=1,
        ).collect(request)
        processed = ProcessingPipeline().process(collection, request)
        result = collection.results[0]
        counts = lambda sub: sum(r.sub_source is sub for r in result.records)
        eligible = lambda sub: sum(r.sub_source is sub and r.eligible_for_analysis for r in result.records)
        output = {
            "yahoo_news": {"connection_success": result.metadata.get("sub_sources", {}).get("yahoo_news_article") != "failed",
                "raw_articles": counts(YahooSubSource.NEWS_ARTICLE), "eligible_articles": eligible(YahooSubSource.NEWS_ARTICLE)},
            "yahoo_comments": {"connection_success": result.metadata.get("sub_sources", {}).get("yahoo_news_comment") != "failed",
                "raw_comments": counts(YahooSubSource.NEWS_COMMENT), "eligible_consumer_voices": eligible(YahooSubSource.NEWS_COMMENT)},
            "chiebukuro": {"connection_success": result.metadata.get("sub_sources", {}).get("yahoo_chiebukuro_question") != "failed",
                "questions": counts(YahooSubSource.CHIEBUKURO_QUESTION), "answers": counts(YahooSubSource.CHIEBUKURO_ANSWER),
                "eligible_consumer_voices": eligible(YahooSubSource.CHIEBUKURO_QUESTION)+eligible(YahooSubSource.CHIEBUKURO_ANSWER)},
            "realtime": {"feasible": False, "availability_reason": result.metadata.get("realtime_availability_reason"), "posts_collected": 0, "eligible_posts": 0},
            "total": {"final_yahoo_records": processed.audit.final_eligible,
                "final_yahoo_consumer_voices": processed.audit.consumer_voice_count, "overall_source_status": result.status.value},
        }
        print(json.dumps(output, ensure_ascii=False))
        return 0
    finally:
        http.close()


if __name__ == "__main__":
    raise SystemExit(main())
