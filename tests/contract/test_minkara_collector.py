from datetime import date, datetime, timezone
import json

import pytest

from japan_voice.collectors.minkara import MinkaraCollector, parse_comments, parse_post, parse_search
from japan_voice.config.settings import Settings
from japan_voice.domain.enums import (
    CollectorStatus, ContentGroup, ContentType, DateSource, EntityMatch,
    MinkaraSubSource, ScopeDecision, Source,
)
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError
from japan_voice.processing.deduplicate import deduplicate
from japan_voice.processing.guardrails import classify_entity, evaluate_record


POST_URL = "https://minkara.carview.co.jp/userid/123/blog/456/"
SEARCH = f'''<ul><li class="common-article-list__list">
<a class="common-article-list__card-link" href="{POST_URL}"></a>
<div class="common-article-list__data-area"><h2 class="common-article-list__title">PV5を日本で見てきました</h2>
<p class="common-article-list__textarea">日本導入モデルのサイズを確認しました</p>
<span class="username">公開ユーザー</span><time class="date" datetime="2026年8月10日">2026年8月10日</time></div>
</li></ul>'''


def detail(*, title="PV5を日本で見てきました", body="日本の駐車場ではサイズが気になります", date_value="2026-08-10T09:00:00+09:00", comments=True):
    payload = {"@context":"https://schema.org", "@type":"BlogPosting", "headline":title,
        "articleBody":body, "datePublished":date_value, "dateModified":date_value,
        "author":{"@type":"Person", "name":"公開ユーザー"}}
    comment = '''<ul class="comment-list"><li data-comment-id="c1"><span class="username">利用者</span>
      <p class="comment-body">このサイズなら欲しい</p><time datetime="2026-08-11T10:00:00+09:00"></time></li></ul>''' if comments else ""
    return f'<script type="application/ld+json">{json.dumps(payload, ensure_ascii=False)}</script>{comment}'


class FakeHttp:
    def __init__(self, *, search=SEARCH, page=None, search_error=None):
        self.search = search; self.page = detail() if page is None else page; self.search_error = search_error
    def get_text(self, url, *, params=None, headers=None):
        if url.endswith("/search/"):
            if self.search_error: raise self.search_error
            return self.search
        if url == POST_URL: return self.page
        raise AssertionError(url)


def settings():
    return Settings(minkara_max_queries=1, minkara_posts_per_query=5, minkara_comments_per_post=5)


def request():
    return SearchRequest(keyword="PV5", start_date=date(2026,8,1), end_date=date(2026,8,16),
        selected_sources=[Source.MINKARA], max_results=5)


def test_public_parsers_map_search_post_and_comments() -> None:
    assert parse_search(SEARCH, 5)[0]["native_id"] == "123:456"
    assert parse_post(detail())["title"].startswith("PV5")
    assert parse_comments(detail(), 5, POST_URL)[0]["native_id"] == "c1"


def test_japan_pv5_post_and_short_parent_comment_are_consumer_voice() -> None:
    result = MinkaraCollector(http=FakeHttp(), settings=settings()).collect(request(), ["PV5 日本"])
    post = next(r for r in result.records if r.sub_source is MinkaraSubSource.POST)
    comment = next(r for r in result.records if r.sub_source is MinkaraSubSource.COMMENT)
    assert result.status is CollectorStatus.SUCCESS
    assert post.content_group is comment.content_group is ContentGroup.CONSUMER_VOICE
    assert post.eligible_for_analysis and comment.eligible_for_analysis
    assert comment.entity_match is EntityMatch.TARGET


@pytest.mark.parametrize(("title", "body", "decision"), [
    ("Kia PV5 USA Review", "United States market only", ScopeDecision.EXCLUDE),
    ("韓国でKia PV5発売", "韓国販売のみ", ScopeDecision.EXCLUDE),
    ("PV5海外仕様との比較", "欧州仕様より日本の駐車場では大きい", ScopeDecision.INCLUDE),
])
def test_market_scope_cases(title, body, decision) -> None:
    record = ContentRecord(id="scope", source=Source.MINKARA, sub_source=MinkaraSubSource.POST,
        provider="みんカラ", content_type=ContentType.POST, keyword="PV5", title=title, content=body,
        published_at=datetime(2026,8,10,tzinfo=timezone.utc), url=POST_URL)
    result = evaluate_record(record, start_date=date(2026,8,1), end_date=date(2026,8,16)).record
    assert result.scope_decision is decision


def test_unrelated_kia_and_pv5_deterministic_entity() -> None:
    assert classify_entity("Saskiaの音楽について", "KIA") is EntityMatch.UNRELATED
    assert classify_entity("PV5 Cargo", "PV5") is EntityMatch.TARGET


def test_missing_post_date_remains_analysis_eligible_without_trend_date() -> None:
    search_without_date = SEARCH.replace('<time class="date" datetime="2026年8月10日">2026年8月10日</time>', '')
    result = MinkaraCollector(http=FakeHttp(search=search_without_date, page=detail(date_value=None, comments=False)), settings=settings()).collect(request(), ["PV5 日本"])
    post = result.records[0]
    assert post.eligible_for_analysis and post.published_at is None and post.analysis_date is None


def test_missing_comment_date_inherits_parent_post_date() -> None:
    html = detail().replace(' datetime="2026-08-11T10:00:00+09:00"', '')
    result = MinkaraCollector(http=FakeHttp(page=html), settings=settings()).collect(request(), ["PV5 日本"])
    comment = next(r for r in result.records if r.sub_source is MinkaraSubSource.COMMENT)
    assert comment.published_at is None and comment.analysis_date is not None
    assert comment.date_source is DateSource.PARENT_POST and comment.eligible_for_analysis


def test_post_and_comment_duplicates_are_removed_safely() -> None:
    post = ContentRecord(id="p", source=Source.MINKARA, sub_source=MinkaraSubSource.POST,
        provider="みんカラ", content_type=ContentType.POST, keyword="PV5", title="PV5 日本発売", url=POST_URL)
    duplicate = post.model_copy(update={"id":"p2"})
    kept, count = deduplicate([post, duplicate]); assert len(kept) == 2 and count == 1
    parent = post.model_copy(update={"eligible_for_analysis":True})
    c1 = ContentRecord(id="c1", source=Source.MINKARA, sub_source=MinkaraSubSource.COMMENT,
        provider="みんカラ", content_type=ContentType.COMMENT, keyword="PV5", content="欲しい", is_comment=True,
        parent_id=parent.id, parent_url=parent.url, native_id="same", url=POST_URL+"#c1")
    c2 = c1.model_copy(update={"id":"c2", "url":POST_URL+"#c2"})
    kept, count = deduplicate([c1,c2]); assert len(kept) == 2 and count == 1


def test_zero_comments_is_success() -> None:
    result = MinkaraCollector(http=FakeHttp(page=detail(comments=False)), settings=settings()).collect(request(), ["PV5 日本"])
    assert result.status is CollectorStatus.SUCCESS and result.records_collected == 1


def test_comment_parser_failure_keeps_post_partial(monkeypatch) -> None:
    def fail(*args, **kwargs): raise ValueError("changed markup")
    monkeypatch.setattr("japan_voice.collectors.minkara.parse_comments", fail)
    result = MinkaraCollector(http=FakeHttp(), settings=settings()).collect(request(), ["PV5 日本"])
    assert result.status is CollectorStatus.PARTIAL
    assert any(r.sub_source is MinkaraSubSource.POST for r in result.records)


def test_permission_failure_is_safe_and_empty_search_succeeds() -> None:
    error = ExternalServiceError(ErrorType.PERMISSION_ERROR, "HTTP 403", status_code=403, retryable=False)
    failed = MinkaraCollector(http=FakeHttp(search_error=error), settings=settings()).collect(request(), ["PV5 日本"])
    assert failed.status is CollectorStatus.PARTIAL and failed.records == []
    empty = MinkaraCollector(http=FakeHttp(search=""), settings=settings()).collect(request(), ["PV5 日本"])
    assert empty.status is CollectorStatus.SUCCESS and empty.records == []


def test_malformed_post_is_partial_safe_failure() -> None:
    result = MinkaraCollector(http=FakeHttp(page="<html>changed</html>"), settings=settings()).collect(request(), ["PV5 日本"])
    assert result.status is CollectorStatus.PARTIAL and result.records == []
