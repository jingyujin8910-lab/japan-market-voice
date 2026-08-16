#!/usr/bin/env python3
"""Minimal public-HTML みんカラ smoke test; never prints source text or PII."""

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from japan_voice.application.collection_service import CollectionOrchestrator
from japan_voice.application.pipeline import ProcessingPipeline
from japan_voice.collectors.minkara import MinkaraCollector
from japan_voice.config.settings import load_settings
from japan_voice.domain.enums import MinkaraSubSource, Source
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.http import HttpClient, HttpClientConfig


def main() -> int:
    settings = replace(load_settings(load_dotenv_file=True), minkara_max_queries=1,
        minkara_posts_per_query=5, minkara_comments_per_post=5)
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    request = SearchRequest(keyword="PV5", start_date=today - timedelta(days=30),
        end_date=today, selected_sources=[Source.MINKARA], max_results=5)
    http = HttpClient(HttpClientConfig.from_settings(settings))
    try:
        collection = CollectionOrchestrator(
            [MinkaraCollector(http=http, settings=settings)], max_queries_per_source=1,
        ).collect(request)
        run = ProcessingPipeline().process(collection, request)
        result = collection.results[0]
        eligible_ids = {record.id for record in run.eligible_records}
        posts = [r for r in run.raw_records if r.sub_source is MinkaraSubSource.POST]
        comments = [r for r in run.raw_records if r.sub_source is MinkaraSubSource.COMMENT]
        output = {
            "connection_success": result.status.value in {"success", "partial"},
            "raw_posts": len(posts), "eligible_posts": sum(r.id in eligible_ids for r in posts),
            "raw_comments": len(comments), "eligible_comments": sum(r.id in eligible_ids for r in comments),
            "final_consumer_voice": run.audit.consumer_voice_count,
            "entity_excluded": run.audit.entity_excluded,
            "foreign_market_excluded": run.audit.japan_scope_excluded,
            "collection_method": result.metadata.get("collection_method", "public_html_json_ld"),
            "source_status": result.status.value,
        }
        print(json.dumps(output, ensure_ascii=False))
        return 0
    finally:
        http.close()


if __name__ == "__main__":
    raise SystemExit(main())
