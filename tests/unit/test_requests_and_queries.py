from datetime import date

import pytest
from pydantic import ValidationError

from japan_voice.application.query_planner import expand_japan_queries
from japan_voice.domain.enums import Source
from japan_voice.domain.requests import SearchRequest


def test_search_request_normalizes_keyword_and_deduplicates_sources() -> None:
    request = SearchRequest(
        keyword="  ＰＶ５  ",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 15),
        selected_sources=[Source.YOUTUBE, Source.YOUTUBE, Source.NEWS],
        max_results=25,
    )
    assert request.keyword == "PV5"
    assert request.selected_sources == [Source.YOUTUBE, Source.NEWS]


@pytest.mark.parametrize(
    "overrides",
    [
        {"keyword": "   "},
        {"end_date": date(2026, 7, 31)},
        {"selected_sources": []},
        {"max_results": 0},
        {"max_results": 1001},
    ],
)
def test_search_request_rejects_invalid_input(overrides: dict) -> None:
    values = {
        "keyword": "PV5",
        "start_date": date(2026, 8, 1),
        "end_date": date(2026, 8, 15),
        "selected_sources": [Source.YOUTUBE],
        "max_results": 100,
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        SearchRequest(**values)


def test_pv5_query_expansion_follows_prd_order_and_limit() -> None:
    queries = expand_japan_queries("PV5", Source.NEWS, max_queries=5)
    assert queries == [
        "PV5 日本", "PV5 日本市場", "PV5 日本発売", "PV5 日本販売", "PV5 キア"
    ]
    assert len(queries) == len(set(queries)) == 5


def test_kia_query_expansion_is_source_specific_and_deduplicated() -> None:
    youtube = expand_japan_queries("KIA", Source.YOUTUBE, max_queries=4)
    news = expand_japan_queries("KIA", Source.NEWS, max_queries=4)
    assert youtube == ["KIA 日本", "KIA 日本発売", "KIA 日本仕様", "KIA 日本 試乗"]
    assert news == ["KIA 日本", "KIA 日本市場", "KIA 日本発売", "KIA 日本販売"]
    assert len(youtube) == len({item.casefold() for item in youtube})


def test_query_expansion_rejects_invalid_limits_and_blank_keyword() -> None:
    with pytest.raises(ValueError):
        expand_japan_queries("PV5", Source.NEWS, max_queries=0)
    with pytest.raises(ValueError):
        expand_japan_queries(" ", Source.NEWS)

