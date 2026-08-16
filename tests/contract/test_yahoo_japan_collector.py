from datetime import date, datetime, timezone
import json

import pytest

from japan_voice.collectors.yahoo_japan import (
    YahooJapanCollector, parse_chiebukuro_detail, parse_chiebukuro_search,
    parse_news_comments, parse_news_search,
)
from japan_voice.config.settings import Settings
from japan_voice.domain.enums import (
    CollectorStatus, ContentGroup, ContentType, DateSource, ScopeDecision, Source, YahooSubSource,
)
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError
from japan_voice.processing.guardrails import evaluate_record


ARTICLE_ID = "a" * 40
ARTICLE_URL = f"https://news.yahoo.co.jp/articles/{ARTICLE_ID}"
QUESTION_URL = "https://detail.chiebukuro.yahoo.co.jp/qa/question_detail/q12345"


def news_search(title="キアPV5、日本市場へ正式導入"):
    return f'''<ol class="newsFeed_list"><li><a href="{ARTICLE_URL}">
      <div class="sc-110wjhy-2">{title}</div>
      <div class="sc-110wjhy-0">日本価格と販売計画を解説</div></a></li></ol>'''


def news_article(title="キアPV5、日本市場へ正式導入"):
    payload = {"@context":"https://schema.org","@type":"NewsArticle","headline":title,
        "description":"日本での発売価格と販売計画","datePublished":"2026-08-10T10:00:00+09:00",
        "publisher":{"name":"テスト新聞"}}
    return f'<script type="application/ld+json">{json.dumps(payload, ensure_ascii=False)}</script>'


COMMENTS = '''<article id="comment-main"><ul><li>
  <a href="https://news.yahoo.co.jp/users/public-user">利用者</a><time>2026/8/11 10:20</time>
  <a href="https://news.yahoo.co.jp/profile/news/comments/comment-1">詳細</a>
  <p class="sc-169yn8p-10">日本では充電インフラがまだ不安</p>
</li></ul></article>'''


CHIE_SEARCH = f'''<ul><li><h3><a href="{QUESTION_URL}">PV5は日本ではいくらになりますか？</a></h3>
<p class="summary">日本発売時の価格を知りたいです。</p><p class="category">自動車</p></li></ul>'''


def chie_detail():
    page = {"@context":"https://schema.org","@type":"QAPage","mainEntity":{
        "@type":"Question","name":"PV5は日本ではいくらになりますか？",
        "datePublished":"2026-08-10T09:00:00+09:00","answerCount":1,
        "acceptedAnswer":{"@type":"Answer","text":"日本価格はまだ正式発表前です。",
            "datePublished":"2026-08-11T09:00:00+09:00","url":QUESTION_URL+"#answer-1",
            "upvoteCount":2}}}
    return f'<script type="application/ld+json">{json.dumps([page], ensure_ascii=False)}</script>'


class FakeHttp:
    def __init__(self, *, comment_error=False, realtime_error=False):
        self.comment_error = comment_error

    def get_text(self, url, *, params=None, headers=None):
        if url.endswith("/search") and "news.yahoo" in url:
            return news_search()
        if url == ARTICLE_URL:
            return news_article()
        if url == ARTICLE_URL + "/comments":
            if self.comment_error:
                raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "comment parser failed")
            return COMMENTS
        if url.endswith("/search") and "chiebukuro" in url:
            return CHIE_SEARCH
        if url == QUESTION_URL:
            return chie_detail()
        raise AssertionError(url)


def request():
    return SearchRequest(keyword="PV5", start_date=date(2026,8,1), end_date=date(2026,8,16),
        selected_sources=[Source.YAHOO_JAPAN], max_results=10)


def settings():
    return Settings(yahoo_max_queries=1, yahoo_news_articles_per_query=3,
        yahoo_comments_per_article=5, yahoo_questions_per_query=3,
        yahoo_answers_per_question=3)


def test_public_parsers_extract_news_comments_and_chiebukuro() -> None:
    assert parse_news_search(news_search(), 3)[0]["native_id"] == ARTICLE_ID
    comment = parse_news_comments(COMMENTS, 5)[0]
    assert comment["native_id"] == "comment-1"
    assert comment["empathy"] == comment["naruhodo"] == comment["hmm"] == 0
    assert parse_chiebukuro_search(CHIE_SEARCH, 3)[0]["native_id"] == "q12345"
    detail = parse_chiebukuro_detail(chie_detail())
    assert detail["answer_count"] == 1 and len(detail["answers"]) == 1


def test_yahoo_collector_maps_all_p0_record_types() -> None:
    result = YahooJapanCollector(http=FakeHttp(), settings=settings()).collect(request(), ["PV5 日本"])
    assert result.status is CollectorStatus.SUCCESS
    assert {record.sub_source for record in result.records} == {
        YahooSubSource.NEWS_ARTICLE, YahooSubSource.NEWS_COMMENT,
        YahooSubSource.CHIEBUKURO_QUESTION, YahooSubSource.CHIEBUKURO_ANSWER,
    }
    article = next(r for r in result.records if r.sub_source is YahooSubSource.NEWS_ARTICLE)
    voices = [r for r in result.records if r.sub_source is not YahooSubSource.NEWS_ARTICLE]
    assert article.content_group is ContentGroup.MARKET_CONTENT
    assert all(record.content_group is ContentGroup.CONSUMER_VOICE for record in voices)
    assert all(record.eligible_for_analysis for record in result.records)
    assert result.metadata["realtime_availability_reason"] == "No stable public collection method"
    assert result.metadata["x_api_used"] is False


def test_comment_failure_keeps_articles_and_chiebukuro_as_partial() -> None:
    result = YahooJapanCollector(http=FakeHttp(comment_error=True), settings=settings()).collect(request(), ["PV5 日本"])
    assert result.status is CollectorStatus.PARTIAL
    assert any(r.sub_source is YahooSubSource.NEWS_ARTICLE for r in result.records)
    assert any(r.sub_source is YahooSubSource.CHIEBUKURO_QUESTION for r in result.records)
    assert not any(r.sub_source is YahooSubSource.NEWS_COMMENT for r in result.records)


@pytest.mark.parametrize(("title", "expected"), [
    ("キアPV5、日本市場へ正式導入", ScopeDecision.INCLUDE),
    ("Kia PV5 launches in the United States", ScopeDecision.EXCLUDE),
    ("韓国でKia PV5販売開始", ScopeDecision.EXCLUDE),
    ("韓国では発売済み、キアPV5は日本で今秋導入", ScopeDecision.INCLUDE),
    ("Saskiaが音楽賞を受賞", ScopeDecision.EXCLUDE),
])
def test_yahoo_article_guardrail_cases(title, expected) -> None:
    record = ContentRecord(id="article", source=Source.YAHOO_JAPAN,
        sub_source=YahooSubSource.NEWS_ARTICLE, provider="Yahoo!ニュース",
        content_type=ContentType.ARTICLE, keyword="PV5", title=title,
        published_at=datetime(2026,8,10,tzinfo=timezone.utc), url=ARTICLE_URL)
    evaluated = evaluate_record(record, start_date=date(2026,8,1), end_date=date(2026,8,16)).record
    if title.startswith("Saskia"):
        assert evaluated.eligible_for_analysis is False
    else:
        assert evaluated.scope_decision is expected


def test_foreign_parent_comment_excluded_and_zero_comments_keep_article() -> None:
    parent = ContentRecord(id="foreign", source=Source.YAHOO_JAPAN,
        sub_source=YahooSubSource.NEWS_ARTICLE, provider="Yahoo!ニュース",
        content_type=ContentType.ARTICLE, keyword="PV5", title="Kia PV5 launches in the United States",
        published_at=datetime(2026,8,10,tzinfo=timezone.utc), url=ARTICLE_URL)
    parent = evaluate_record(parent,start_date=date(2026,8,1),end_date=date(2026,8,16)).record
    comment = ContentRecord(id="comment",source=Source.YAHOO_JAPAN,
        sub_source=YahooSubSource.NEWS_COMMENT,provider="Yahoo!ニュース",
        content_type=ContentType.COMMENT,content_group=ContentGroup.CONSUMER_VOICE,
        keyword="PV5",title=parent.title,content="日本語のコメント",parent_id=parent.id,
        parent_url=parent.url,url=ARTICLE_URL+"/comments",is_comment=True,
        published_at=datetime(2026,8,11,tzinfo=timezone.utc))
    child=evaluate_record(comment,start_date=date(2026,8,1),end_date=date(2026,8,16),parent=parent).record
    assert parent.eligible_for_analysis is False and child.eligible_for_analysis is False
    assert parse_news_comments("<article id='comment-main'><ul></ul></article>",5) == []


def test_missing_question_date_and_answer_metadata_are_safe() -> None:
    payload = {"@type":"QAPage","mainEntity":{"@type":"Question","name":"PV5 日本価格","answerCount":1,
        "suggestedAnswer":[{"@type":"Answer","text":"まだ不明です"}]}}
    detail=parse_chiebukuro_detail(f'<script type="application/ld+json">{json.dumps(payload,ensure_ascii=False)}</script>')
    assert detail["published_at"] is None
    assert detail["answers"][0].get("datePublished") is None


def test_japan_article_japanese_comment_is_consumer_voice() -> None:
    result = YahooJapanCollector(http=FakeHttp(), settings=settings()).collect(request(), ["PV5 日本"])
    comment = next(r for r in result.records if r.sub_source is YahooSubSource.NEWS_COMMENT)
    assert comment.content_group is ContentGroup.CONSUMER_VOICE
    assert comment.eligible_for_analysis is True


def _dated_yahoo_parent(published_at=datetime(2026, 8, 10, tzinfo=timezone.utc)):
    parent = ContentRecord(id="dated-parent", source=Source.YAHOO_JAPAN,
        sub_source=YahooSubSource.NEWS_ARTICLE, provider="Yahoo!ニュース",
        content_type=ContentType.ARTICLE, keyword="PV5", title="キアPV5、日本で発売",
        published_at=published_at, url=ARTICLE_URL)
    return evaluate_record(parent, start_date=date(2026,8,1), end_date=date(2026,8,16)).record


def _yahoo_comment(parent, published_at):
    return ContentRecord(id="dated-comment", source=Source.YAHOO_JAPAN,
        sub_source=YahooSubSource.NEWS_COMMENT, provider="Yahoo!ニュース",
        content_type=ContentType.COMMENT, content_group=ContentGroup.CONSUMER_VOICE,
        keyword="PV5", title=parent.title, content="日本で欲しい", parent_id=parent.id,
        parent_url=parent.url, url=ARTICLE_URL + "/comments/dated", is_comment=True,
        published_at=published_at)


def test_yahoo_comment_uses_known_comment_date_for_analysis_and_trend() -> None:
    parent = _dated_yahoo_parent()
    child = evaluate_record(_yahoo_comment(parent, datetime(2026,8,11,tzinfo=timezone.utc)),
        start_date=date(2026,8,1), end_date=date(2026,8,16), parent=parent).record
    assert child.eligible_for_analysis and child.analysis_date == child.published_at
    assert child.date_source is DateSource.COMMENT


def test_yahoo_comment_with_known_out_of_range_date_is_excluded() -> None:
    parent = _dated_yahoo_parent()
    child = evaluate_record(_yahoo_comment(parent, datetime(2026,7,1,tzinfo=timezone.utc)),
        start_date=date(2026,8,1), end_date=date(2026,8,16), parent=parent).record
    assert child.eligible_for_analysis is False


def test_yahoo_comment_without_date_inherits_parent_analysis_date_only() -> None:
    parent = _dated_yahoo_parent()
    child = evaluate_record(_yahoo_comment(parent, None), start_date=date(2026,8,1),
        end_date=date(2026,8,16), parent=parent).record
    assert child.eligible_for_analysis and child.published_at is None
    assert child.analysis_date == parent.published_at
    assert child.date_source is DateSource.PARENT_ARTICLE


def test_chiebukuro_pv5_question_and_short_answer_inherit_entity_context() -> None:
    question = ContentRecord(id="pv5-question", source=Source.YAHOO_JAPAN,
        sub_source=YahooSubSource.CHIEBUKURO_QUESTION, provider="Yahoo!知恵袋",
        content_type=ContentType.QUESTION, keyword="PV5", title="PV5は日本でいつ発売されますか?",
        published_at=datetime(2026,8,10,tzinfo=timezone.utc), url=QUESTION_URL)
    question = evaluate_record(question, start_date=date(2026,8,1), end_date=date(2026,8,16)).record
    answer = ContentRecord(id="short-answer", source=Source.YAHOO_JAPAN,
        sub_source=YahooSubSource.CHIEBUKURO_ANSWER, provider="Yahoo!知恵袋",
        content_type=ContentType.ANSWER, keyword="PV5", title=None, content="今年の秋だと思います。",
        parent_id=question.id, parent_url=question.url, published_at=datetime(2026,8,11,tzinfo=timezone.utc),
        url=QUESTION_URL + "?answer=1")
    answer = evaluate_record(answer, start_date=date(2026,8,1), end_date=date(2026,8,16), parent=question).record
    assert question.content_group is ContentGroup.CONSUMER_VOICE and question.eligible_for_analysis
    assert answer.content_group is ContentGroup.CONSUMER_VOICE and answer.eligible_for_analysis


def test_unrelated_kia_question_is_excluded() -> None:
    question = ContentRecord(id="unrelated", source=Source.YAHOO_JAPAN,
        sub_source=YahooSubSource.CHIEBUKURO_QUESTION, provider="Yahoo!知恵袋",
        content_type=ContentType.QUESTION, keyword="KIA", title="Saskiaの音楽について",
        content="日本の音楽賞の質問", published_at=datetime(2026,8,10,tzinfo=timezone.utc),
        url=QUESTION_URL)
    result=evaluate_record(question,start_date=date(2026,8,1),end_date=date(2026,8,16)).record
    assert result.eligible_for_analysis is False


def test_realtime_unavailable_does_not_remove_p0_records() -> None:
    result = YahooJapanCollector(http=FakeHttp(), settings=settings()).collect(request(), ["PV5 日本"])
    assert result.metadata["sub_sources"]["yahoo_realtime_post"] == "unavailable"
    assert result.records_collected >= 4
    assert result.metadata["x_api_used"] is False


def test_news_zero_comments_still_returns_article() -> None:
    class ZeroCommentHttp(FakeHttp):
        def get_text(self, url, *, params=None, headers=None):
            if url == ARTICLE_URL + "/comments":
                return "<article id='comment-main'><ul></ul></article>"
            return super().get_text(url, params=params, headers=headers)
    result=YahooJapanCollector(http=ZeroCommentHttp(),settings=settings()).collect(request(),["PV5 日本"])
    assert any(r.sub_source is YahooSubSource.NEWS_ARTICLE for r in result.records)
    assert not any(r.sub_source is YahooSubSource.NEWS_COMMENT for r in result.records)


def test_news_comments_follow_all_public_pages() -> None:
    def comment_page(start: int, count: int) -> str:
        items = "".join(
            f'''<li><a href="https://news.yahoo.co.jp/users/user-{index}">利用者</a>
            <time>2026/8/11 10:20</time>
            <a href="https://news.yahoo.co.jp/profile/news/comments/comment-{index}">詳細</a>
            <p class="sc-169yn8p-10">日本でPV5を使いたい {index}</p></li>'''
            for index in range(start, start + count)
        )
        return f'<article id="comment-main"><ul>{items}</ul></article>'

    class PaginatedHttp(FakeHttp):
        def __init__(self):
            super().__init__()
            self.comment_pages = []

        def get_text(self, url, *, params=None, headers=None):
            if url == ARTICLE_URL + "/comments":
                page = (params or {}).get("page", 1)
                self.comment_pages.append(page)
                return {1: comment_page(1, 10), 2: comment_page(11, 10), 3: comment_page(21, 7)}[page]
            return super().get_text(url, params=params, headers=headers)

    http = PaginatedHttp()
    configured = Settings(
        yahoo_max_queries=1, yahoo_news_articles_per_query=3,
        yahoo_comments_per_article=100, yahoo_comment_max_pages=10,
        yahoo_questions_per_query=3, yahoo_answers_per_question=3,
    )
    result = YahooJapanCollector(http=http, settings=configured).collect(request(), ["PV5 日本"])
    comments = [r for r in result.records if r.sub_source is YahooSubSource.NEWS_COMMENT]
    assert len(comments) == 27
    assert http.comment_pages == [1, 2, 3]
    assert result.metadata["news_comment_pages_requested"] == 3
    assert result.metadata["news_comment_article_audit"][0]["collection_stop_reason"] == "pagination_exhausted"
