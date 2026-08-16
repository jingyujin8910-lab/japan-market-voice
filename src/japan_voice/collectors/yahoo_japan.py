"""Yahoo Japan public-web collector with isolated sub-source failures.

No private API, login automation, browser automation, or access-control bypass
is used. Selectors intentionally rely on semantic containers and JSON-LD where
available; a sub-source failure never discards records from another one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import unescape
import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup

from japan_voice.config.settings import Settings
from japan_voice.domain.enums import (
    CollectorStatus, ContentGroup, ContentType, Source, YahooSubSource,
)
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError
from japan_voice.infrastructure.http import HttpClient
from japan_voice.processing.deduplicate import deduplicate
from japan_voice.processing.guardrails import evaluate_record
from .base import CollectorResult


NEWS_SEARCH = "https://news.yahoo.co.jp/search"
CHIEBUKURO_SEARCH = "https://chiebukuro.yahoo.co.jp/search"
USER_AGENT = "Mozilla/5.0 (compatible; JapanMarketVoice/1.0; Streamlit MVP)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "ja-JP,ja;q=0.9"}
_ARTICLE_ID = re.compile(r"/articles/([0-9a-f]+)")
_QUESTION_ID = re.compile(r"question_detail/(q\d+)")


def _canonical(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme or "https", parts.netloc, parts.path, "", ""))


def _int(text: str) -> int:
    match = re.search(r"([\d,]+)", text or "")
    return int(match.group(1).replace(",", "")) if match else 0


def _datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone(timedelta(hours=9)))
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    now_jst = datetime.now(timezone(timedelta(hours=9)))
    relative = re.search(r"(\d+)日前", text)
    if relative:
        return (now_jst - timedelta(days=int(relative.group(1)))).astimezone(timezone.utc)
    match = re.search(r"(?:(\d{4})[年/])?(\d{1,2})[月/](\d{1,2})日?(?:\([^)]*\))?\s*(\d{1,2})?[:時]?(\d{2})?", text)
    if not match:
        return None
    year, month, day, hour, minute = match.groups()
    try:
        return datetime(
            int(year or now_jst.year), int(month), int(day), int(hour or 0), int(minute or 0),
            tzinfo=timezone(timedelta(hours=9)),
        ).astimezone(timezone.utc)
    except ValueError:
        return None


def _json_ld(soup: BeautifulSoup) -> List[Mapping[str, Any]]:
    output: List[Mapping[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            value = json.loads(unescape(script.get_text()))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        values = value if isinstance(value, list) else [value]
        output.extend(item for item in values if isinstance(item, dict))
    return output


def parse_news_search(html: str, limit: int) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    output: List[Dict[str, str]] = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        match = _ARTICLE_ID.search(anchor["href"])
        if not match or match.group(1) in seen:
            continue
        seen.add(match.group(1))
        item = anchor.find_parent("li") or anchor
        title_node = item.select_one("div[class*='sc-110wjhy-2']")
        snippet_node = item.select_one("div[class*='sc-110wjhy-0']")
        title = (title_node or anchor).get_text(" ", strip=True)
        if not title:
            continue
        output.append({
            "native_id": match.group(1), "url": _canonical(anchor["href"]),
            "title": title, "snippet": snippet_node.get_text(" ", strip=True) if snippet_node else "",
        })
        if len(output) >= limit:
            break
    return output


def parse_news_article(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    article = next((item for item in _json_ld(soup) if item.get("@type") == "NewsArticle"), None)
    if article is None:
        raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "Yahoo News article JSON-LD is missing")
    publisher = article.get("publisher") or {}
    author = article.get("author") or {}
    return {
        "title": str(article.get("headline") or ""),
        "content": str(article.get("description") or ""),
        "published_at": _datetime(article.get("datePublished")),
        "publisher": str(publisher.get("name") or author.get("name") or "Yahoo!ニュース"),
    }


def parse_news_comments(html: str, limit: int) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#comment-main")
    if root is None:
        return []
    output: List[Dict[str, Any]] = []
    for item in root.select(":scope > ul > li"):
        text_node = item.select_one("p[class*='sc-169yn8p-10']")
        profile = item.select_one("a[href*='/profile/news/comments/']")
        if text_node is None or profile is None:
            continue
        comment_id = profile.get("href", "").rstrip("/").split("/")[-1]
        if not comment_id:
            continue
        reactions = {"empathy": 0, "naruhodo": 0, "hmm": 0}
        for label, key in (("共感した", "empathy"), ("なるほど", "naruhodo"), ("うーん", "hmm")):
            marker = item.find(string=lambda value: isinstance(value, str) and label in value)
            if marker:
                reactions[key] = _int(marker.parent.parent.get_text(" ", strip=True))
        time_node = item.find("time")
        author_node = item.select_one("a[href*='/users/']")
        output.append({
            "native_id": comment_id,
            "content": text_node.get_text(" ", strip=True),
            "author": author_node.get_text(" ", strip=True) if author_node else None,
            "published_at": _datetime(time_node.get_text(" ", strip=True) if time_node else None),
            "url": _canonical(profile["href"]),
            **reactions,
        })
        if len(output) >= limit:
            break
    return output


def parse_chiebukuro_search(html: str, limit: int) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    output: List[Dict[str, str]] = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        match = _QUESTION_ID.search(anchor["href"])
        if not match or match.group(1) in seen:
            continue
        seen.add(match.group(1))
        item = anchor.find_parent("li") or anchor
        summary = item.select_one("p[class*='summary']")
        category = item.select_one("p[class*='category']")
        output.append({
            "native_id": match.group(1), "url": _canonical(anchor["href"]),
            "title": anchor.get_text(" ", strip=True),
            "summary": summary.get_text(" ", strip=True) if summary else "",
            "category": category.get_text(" ", strip=True) if category else "",
        })
        if len(output) >= limit:
            break
    return output


def parse_chiebukuro_detail(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    page = next((item for item in _json_ld(soup) if item.get("@type") == "QAPage"), None)
    question = page.get("mainEntity") if page else None
    if not isinstance(question, dict):
        raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "Yahoo Chiebukuro QAPage JSON-LD is missing")
    answers: List[Mapping[str, Any]] = []
    accepted = question.get("acceptedAnswer")
    suggested = question.get("suggestedAnswer") or []
    if isinstance(accepted, dict):
        answers.append(accepted)
    if isinstance(suggested, list):
        answers.extend(item for item in suggested if isinstance(item, dict))
    unique: List[Mapping[str, Any]] = []
    seen = set()
    for answer in answers:
        key = str(answer.get("url") or answer.get("text") or "")
        if key and key not in seen:
            seen.add(key); unique.append(answer)
    return {
        "title": str(question.get("name") or ""),
        "published_at": _datetime(question.get("datePublished")),
        "answer_count": int(question.get("answerCount") or len(unique)),
        "answers": unique,
    }


class YahooJapanCollector:
    source = Source.YAHOO_JAPAN

    def __init__(self, *, http: HttpClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def collect(self, request: SearchRequest, queries: Sequence[str]) -> CollectorResult:
        records: List[ContentRecord] = []
        errors: List[ExternalServiceError] = []
        audit: Dict[str, Any] = {
            "news_articles_raw": 0, "news_comments_raw": 0,
            "news_comment_pages_requested": 0, "news_comment_article_audit": [],
            "chiebukuro_questions_raw": 0, "chiebukuro_answers_raw": 0,
            "realtime_posts_raw": 0,
            "sub_sources": {
                "yahoo_news_article": "success", "yahoo_news_comment": "success",
                "yahoo_chiebukuro_question": "success", "yahoo_chiebukuro_answer": "success",
                "yahoo_realtime_post": "unavailable",
            },
            "realtime_availability_reason": "No stable public collection method",
            "x_api_used": False,
        }
        bounded = list(queries[: self._settings.yahoo_max_queries])
        self._collect_news(request, bounded, records, errors, audit)
        self._collect_chiebukuro(request, bounded, records, errors, audit)
        records, duplicates = deduplicate(records)
        audit["duplicates_removed"] = duplicates
        for sub_source, key in (
            (YahooSubSource.NEWS_ARTICLE, "news_articles_eligible"),
            (YahooSubSource.NEWS_COMMENT, "news_comments_eligible"),
            (YahooSubSource.CHIEBUKURO_QUESTION, "chiebukuro_questions_eligible"),
            (YahooSubSource.CHIEBUKURO_ANSWER, "chiebukuro_answers_eligible"),
            (YahooSubSource.REALTIME_POST, "realtime_posts_eligible"),
        ):
            audit[key] = sum(r.sub_source is sub_source and r.eligible_for_analysis for r in records)
        audit["final_yahoo_records"] = sum(r.eligible_for_analysis for r in records)
        audit["final_yahoo_consumer_voice"] = sum(
            r.eligible_for_analysis and r.content_group is ContentGroup.CONSUMER_VOICE for r in records
        )
        if errors:
            return CollectorResult.partial(self.source, records, errors[0], metadata=audit)
        result = CollectorResult.success(self.source, records)
        result.metadata = audit
        return result

    def _get(self, url: str, *, params: Optional[Mapping[str, Any]] = None) -> str:
        return self._http.get_text(url, params=params, headers=HEADERS)

    def _collect_news(self, request, queries, records, errors, audit) -> None:
        seen = set()
        for query in queries:
            try:
                candidates = parse_news_search(
                    self._get(NEWS_SEARCH, params={"p": query, "ei": "utf-8"}),
                    self._settings.yahoo_news_articles_per_query,
                )
            except ExternalServiceError as error:
                errors.append(error); audit["sub_sources"]["yahoo_news_article"] = "failed"; continue
            for candidate in candidates:
                if candidate["native_id"] in seen:
                    continue
                seen.add(candidate["native_id"])
                try:
                    detail = parse_news_article(self._get(candidate["url"]))
                    article = ContentRecord(
                        id=f"yahoo_japan:news:{candidate['native_id']}", source=self.source,
                        sub_source=YahooSubSource.NEWS_ARTICLE, provider=detail["publisher"],
                        native_id=candidate["native_id"], content_type=ContentType.ARTICLE,
                        content_group=ContentGroup.MARKET_CONTENT, keyword=request.keyword,
                        query_used=query, title=detail["title"] or candidate["title"],
                        content=detail["content"] or candidate["snippet"], published_at=detail["published_at"],
                        url=candidate["url"], raw_metadata={"category": None},
                    )
                    article = evaluate_record(article, start_date=request.start_date, end_date=request.end_date).record
                    records.append(article); audit["news_articles_raw"] += 1
                    if article.eligible_for_analysis:
                        self._collect_comments(request, article, records, errors, audit)
                except ExternalServiceError as error:
                    errors.append(error); audit["sub_sources"]["yahoo_news_article"] = "partial"

    def _collect_comments(self, request, parent, records, errors, audit) -> None:
        try:
            comments: List[Dict[str, Any]] = []
            seen_ids = set()
            stop_reason = "page_limit"
            comment_url = str(parent.url).rstrip("/") + "/comments"
            for page in range(1, self._settings.yahoo_comment_max_pages + 1):
                remaining = self._settings.yahoo_comments_per_article - len(comments)
                if remaining <= 0:
                    stop_reason = "safety_limit"
                    break
                html = self._get(comment_url, params={"page": page} if page > 1 else None)
                audit["news_comment_pages_requested"] += 1
                page_comments = parse_news_comments(html, min(remaining, 100))
                new_comments = [item for item in page_comments if item["native_id"] not in seen_ids]
                if not new_comments:
                    stop_reason = "pagination_exhausted"
                    break
                comments.extend(new_comments)
                seen_ids.update(item["native_id"] for item in new_comments)
                # Yahoo currently exposes ten top-level comments per page. A
                # shorter page is the terminal page and needs no extra request.
                if len(page_comments) < 10:
                    stop_reason = "pagination_exhausted"
                    break
            for item in comments:
                record = ContentRecord(
                    id=f"yahoo_japan:comment:{item['native_id']}", source=self.source,
                    sub_source=YahooSubSource.NEWS_COMMENT, provider="Yahoo!ニュース",
                    native_id=item["native_id"], parent_id=parent.id,
                    content_type=ContentType.COMMENT, content_group=ContentGroup.CONSUMER_VOICE,
                    keyword=request.keyword, query_used=parent.query_used, title=parent.title,
                    content=item["content"], author=item["author"], published_at=item["published_at"],
                    url=item["url"], parent_url=parent.url, is_comment=True,
                    raw_metadata={"reaction_empathy": item["empathy"], "reaction_naruhodo": item["naruhodo"], "reaction_hmm": item["hmm"]},
                )
                records.append(evaluate_record(record, start_date=request.start_date, end_date=request.end_date, parent=parent).record)
                audit["news_comments_raw"] += 1
            audit["news_comment_article_audit"].append({
                "article_id": parent.native_id,
                "comments_collected": len(comments),
                "collection_stop_reason": stop_reason,
            })
        except ExternalServiceError as error:
            errors.append(error); audit["sub_sources"]["yahoo_news_comment"] = "partial"

    def _collect_chiebukuro(self, request, queries, records, errors, audit) -> None:
        seen = set()
        for query in queries:
            try:
                candidates = parse_chiebukuro_search(
                    self._get(CHIEBUKURO_SEARCH, params={"p": query}),
                    self._settings.yahoo_questions_per_query,
                )
            except ExternalServiceError as error:
                errors.append(error); audit["sub_sources"]["yahoo_chiebukuro_question"] = "failed"; continue
            for candidate in candidates:
                if candidate["native_id"] in seen:
                    continue
                seen.add(candidate["native_id"])
                try:
                    detail = parse_chiebukuro_detail(self._get(candidate["url"]))
                    question = ContentRecord(
                        id=f"yahoo_japan:question:{candidate['native_id']}", source=self.source,
                        sub_source=YahooSubSource.CHIEBUKURO_QUESTION, provider="Yahoo!知恵袋",
                        native_id=candidate["native_id"], content_type=ContentType.QUESTION,
                        content_group=ContentGroup.CONSUMER_VOICE, keyword=request.keyword, query_used=query,
                        title=detail["title"] or candidate["title"], content=candidate["summary"],
                        published_at=detail["published_at"], url=candidate["url"],
                        raw_metadata={"category": candidate["category"], "answer_count": detail["answer_count"]},
                    )
                    question = evaluate_record(question, start_date=request.start_date, end_date=request.end_date).record
                    records.append(question); audit["chiebukuro_questions_raw"] += 1
                    if question.eligible_for_analysis:
                        self._answers(request, question, detail["answers"], records, audit)
                except ExternalServiceError as error:
                    errors.append(error); audit["sub_sources"]["yahoo_chiebukuro_question"] = "partial"

    def _answers(self, request, parent, answers, records, audit) -> None:
        for index, answer in enumerate(answers[: self._settings.yahoo_answers_per_question]):
            text = str(answer.get("text") or "").strip()
            if not text:
                continue
            url = str(answer.get("url") or parent.url)
            native_id = url.rstrip("/").split("/")[-1] if "answer" in url else f"{parent.native_id}:{index}"
            answer_url = _canonical(url)
            if answer_url == _canonical(str(parent.url)):
                answer_url = f"{answer_url}?answer={native_id}"
            author = answer.get("author") or {}
            record = ContentRecord(
                id=f"yahoo_japan:answer:{native_id}", source=self.source,
                sub_source=YahooSubSource.CHIEBUKURO_ANSWER, provider="Yahoo!知恵袋",
                native_id=native_id, parent_id=parent.id, content_type=ContentType.ANSWER,
                content_group=ContentGroup.CONSUMER_VOICE, keyword=request.keyword,
                query_used=parent.query_used, title=parent.title, content=text,
                author=str(author.get("name")) if isinstance(author, dict) and author.get("name") else None,
                published_at=_datetime(answer.get("datePublished")), url=answer_url, parent_url=parent.url,
                raw_metadata={"upvote_count": int(answer.get("upvoteCount") or 0), "best_answer": index == 0},
            )
            records.append(evaluate_record(record, start_date=request.start_date, end_date=request.end_date, parent=parent).record)
            audit["chiebukuro_answers_raw"] += 1
