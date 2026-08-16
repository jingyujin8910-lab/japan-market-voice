#!/usr/bin/env python3
"""Minimal manual YouTube smoke test with secret-safe aggregate output only."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from typing import Any, Dict
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from japan_voice.application.query_planner import expand_japan_queries
from japan_voice.collectors.youtube import YouTubeCollector
from japan_voice.config.settings import get_secret, load_settings
from japan_voice.domain.enums import CollectorStatus, ContentGroup, ContentType, ScopeDecision, Source
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.http import HttpClient, HttpClientConfig


def _safe_failure(error_type: str) -> Dict[str, Any]:
    return {
        "api_connection_success": False,
        "keyword": "PV5",
        "videos_found": 0,
        "japan_guardrail_passed_videos": 0,
        "comments_collected": 0,
        "eligible_records": 0,
        "partial_or_failure": True,
        "error_type": error_type,
    }


def main() -> int:
    settings = load_settings(load_dotenv_file=True)
    api_key = get_secret("YOUTUBE_API_KEY")
    if not api_key:
        print(json.dumps(_safe_failure("authentication_error"), ensure_ascii=False))
        return 2

    smoke_settings = replace(
        settings,
        youtube_max_videos=1,
        youtube_comments_per_video=2,
        youtube_comment_safety_limit=2,
        youtube_comment_max_pages=1,
        max_query_variants_per_source=1,
    )
    today_jst = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    request = SearchRequest(
        keyword="PV5",
        start_date=today_jst - timedelta(days=365),
        end_date=today_jst,
        selected_sources=[Source.YOUTUBE],
        max_results=1,
    )
    # Use one high-precision variant produced by the existing QueryPlanner.
    planned = expand_japan_queries(
        request.keyword,
        Source.YOUTUBE,
        max_queries=3,
    )
    queries = [next((query for query in planned if "日本発売" in query), planned[0])]

    http = HttpClient(HttpClientConfig.from_settings(smoke_settings))
    try:
        result = YouTubeCollector(
            http=http,
            settings=smoke_settings,
            api_key=api_key,
        ).collect(request, queries)
    finally:
        http.close()

    videos = [record for record in result.records if record.content_type is ContentType.VIDEO]
    passed_videos = [
        record for record in videos
        if record.scope_decision is ScopeDecision.INCLUDE
    ]
    comments = [
        record for record in result.records
        if record.content_group is ContentGroup.CONSUMER_VOICE
    ]
    output = {
        "api_connection_success": result.status is not CollectorStatus.FAILED,
        "keyword": request.keyword,
        "videos_found": len(videos),
        "japan_guardrail_passed_videos": len(passed_videos),
        "comments_collected": len(comments),
        "eligible_records": sum(record.eligible_for_analysis for record in result.records),
        "partial_or_failure": result.status is not CollectorStatus.SUCCESS,
        "error_type": result.error_type,
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0 if result.status is not CollectorStatus.FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())
