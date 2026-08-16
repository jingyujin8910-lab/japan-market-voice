"""Public-HTML みんカラ collector with isolated comment failures."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import unescape
import json
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from japan_voice.config.settings import Settings
from japan_voice.domain.enums import (
    CollectorStatus, ContentGroup, ContentType, MinkaraSubSource, Source,
)
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError
from japan_voice.infrastructure.http import HttpClient
from japan_voice.processing.deduplicate import deduplicate
from japan_voice.processing.guardrails import evaluate_record
from .base import CollectorResult


SEARCH_URL = "https://minkara.carview.co.jp/search/"
BASE_URL = "https://minkara.carview.co.jp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JapanMarketVoice/1.0)",
    "Accept-Language": "ja-JP,ja;q=0.9",
}
POST_ID = re.compile(r"/userid/(\d+)/(blog)/(\d+)/?$")


def _canonical(value: str) -> str:
    url = urljoin(BASE_URL, value)
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/") + "/", "", ""))


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
    match = re.search(r"(\d{4})[年/.-](\d{1,2})[月/.-](\d{1,2})", text)
    if not match:
        return None
    try:
        return datetime(*map(int, match.groups()), tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
    except ValueError:
        return None


def _json_ld(soup: BeautifulSoup, kind: str) -> Optional[Mapping[str, Any]]:
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(unescape(node.string or node.get_text()))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        values = payload if isinstance(payload, list) else [payload]
        for item in values:
            if isinstance(item, dict) and item.get("@type") == kind:
                return item
    return None


def parse_search(html: str, limit: int) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    output: List[Dict[str, Any]] = []
    seen = set()
    for card in soup.select("li.common-article-list__list"):
        link = card.select_one("a.common-article-list__card-link[href]")
        if not link:
            continue
        url = _canonical(link["href"])
        match = POST_ID.search(url.rstrip("/"))
        if not match or url in seen:
            continue
        seen.add(url)
        title = card.select_one(".common-article-list__title")
        snippet = card.select_one(".common-article-list__textarea")
        author = card.select_one(".username")
        date_node = card.select_one("time.date") or card.select_one(".date")
        output.append({
            "native_id": f"{match.group(1)}:{match.group(3)}",
            "url": url,
            "title": title.get_text(" ", strip=True) if title else "",
            "snippet": snippet.get_text(" ", strip=True) if snippet else "",
            "author": author.get_text(" ", strip=True) if author else None,
            "published_at": _datetime((date_node.get("datetime") or date_node.get_text(" ", strip=True)) if date_node else None),
        })
        if len(output) >= limit:
            break
    return output


def parse_post(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    post = _json_ld(soup, "BlogPosting")
    if not post:
        raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "Minkara post metadata was not found")
    author = post.get("author") or {}
    return {
        "title": str(post.get("headline") or "").strip(),
        "content": str(post.get("articleBody") or post.get("description") or "").strip(),
        "author": str(author.get("name") or "").strip() if isinstance(author, dict) else None,
        "published_at": _datetime(post.get("datePublished")),
        "updated_at": _datetime(post.get("dateModified")),
        "category": None,
    }


def parse_comments(html: str, limit: int, parent_url: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    output: List[Dict[str, Any]] = []
    seen = set()
    selectors = ".comment-entry, .commentList li, .comment-list li, [data-comment-id]"
    for index, node in enumerate(soup.select(selectors)):
        body = node.select_one(".comment-body, .commentText, .comment-text, .body") or node
        content = body.get_text(" ", strip=True)
        if not content:
            continue
        native_id = str(node.get("data-comment-id") or node.get("id") or f"{index + 1}")
        key = (native_id, content)
        if key in seen:
            continue
        seen.add(key)
        author = node.select_one(".username, .comment-author, .user-name")
        date_node = node.select_one("time, .date, .comment-date")
        output.append({
            "native_id": native_id,
            "content": content,
            "author": author.get_text(" ", strip=True) if author else None,
            "published_at": _datetime((date_node.get("datetime") or date_node.get_text(" ", strip=True)) if date_node else None),
            "url": f"{parent_url}#comment-{native_id}",
        })
        if len(output) >= limit:
            break
    return output


class MinkaraCollector:
    source = Source.MINKARA

    def __init__(self, *, http: HttpClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def _get(self, url: str, *, params: Optional[Mapping[str, Any]] = None) -> str:
        return self._http.get_text(url, params=params, headers=HEADERS)

    def collect(self, request: SearchRequest, queries: Sequence[str]) -> CollectorResult:
        records: List[ContentRecord] = []
        errors: List[ExternalServiceError] = []
        audit: Dict[str, Any] = {
            "minkara_posts_raw": 0, "minkara_comments_raw": 0,
            "sub_sources": {"minkara_post": "success", "minkara_comment": "success"},
            "collection_method": "public_html_json_ld",
            "api_or_credential_required": False,
        }
        seen = set()
        for query in list(queries[: self._settings.minkara_max_queries]):
            try:
                candidates = parse_search(
                    self._get(SEARCH_URL, params={"q": query}),
                    self._settings.minkara_posts_per_query,
                )
            except ExternalServiceError as error:
                errors.append(error); audit["sub_sources"]["minkara_post"] = "failed"; continue
            for candidate in candidates:
                if candidate["native_id"] in seen:
                    continue
                seen.add(candidate["native_id"])
                try:
                    html = self._get(candidate["url"])
                    detail = parse_post(html)
                    post = ContentRecord(
                        id=f"minkara:post:{candidate['native_id']}", source=self.source,
                        sub_source=MinkaraSubSource.POST, provider="みんカラ",
                        native_id=candidate["native_id"], content_type=ContentType.POST,
                        content_group=ContentGroup.CONSUMER_VOICE, keyword=request.keyword,
                        query_used=query, title=detail["title"] or candidate["title"],
                        content=detail["content"] or candidate["snippet"],
                        author=detail["author"] or candidate["author"],
                        published_at=detail["published_at"] or candidate["published_at"],
                        url=candidate["url"], raw_metadata={
                            "updated_at": detail["updated_at"].isoformat() if detail["updated_at"] else None,
                            "category": detail["category"], "vehicle_metadata": None,
                        },
                    )
                    post = evaluate_record(post, start_date=request.start_date, end_date=request.end_date).record
                    records.append(post); audit["minkara_posts_raw"] += 1
                    if post.eligible_for_analysis:
                        self._collect_comments(request, post, html, records, errors, audit)
                except ExternalServiceError as error:
                    errors.append(error); audit["sub_sources"]["minkara_post"] = "partial"
        records, duplicates = deduplicate(records)
        audit["duplicates_removed"] = duplicates
        audit["minkara_posts_eligible"] = sum(r.sub_source is MinkaraSubSource.POST and r.eligible_for_analysis for r in records)
        audit["minkara_comments_eligible"] = sum(r.sub_source is MinkaraSubSource.COMMENT and r.eligible_for_analysis for r in records)
        audit["entity_excluded"] = sum(bool(r.exclusion_reason) and r.exclusion_reason.value.startswith("entity_") for r in records)
        audit["foreign_market_excluded"] = sum(bool(r.exclusion_reason) and r.exclusion_reason.value == "foreign_market" for r in records)
        audit["language_excluded"] = sum(bool(r.exclusion_reason) and r.exclusion_reason.value in {"non_japanese", "language_unknown"} for r in records)
        audit["date_excluded"] = sum(bool(r.exclusion_reason) and r.exclusion_reason.value in {"date_unknown", "date_out_of_range"} for r in records)
        audit["final_minkara_records"] = sum(r.eligible_for_analysis for r in records)
        audit["final_minkara_consumer_voice"] = audit["final_minkara_records"]
        if errors:
            return CollectorResult.partial(self.source, records, errors[0], metadata=audit)
        result = CollectorResult.success(self.source, records); result.metadata = audit
        return result

    def _collect_comments(self, request, parent, html, records, errors, audit) -> None:
        try:
            for item in parse_comments(html, self._settings.minkara_comments_per_post, str(parent.url)):
                comment = ContentRecord(
                    id=f"minkara:comment:{parent.native_id}:{item['native_id']}", source=self.source,
                    sub_source=MinkaraSubSource.COMMENT, provider="みんカラ",
                    native_id=item["native_id"], parent_id=parent.id,
                    content_type=ContentType.COMMENT, content_group=ContentGroup.CONSUMER_VOICE,
                    keyword=request.keyword, query_used=parent.query_used, title=parent.title,
                    content=item["content"], author=item["author"], published_at=item["published_at"],
                    url=item["url"], parent_url=parent.url, is_comment=True,
                )
                records.append(evaluate_record(comment, start_date=request.start_date, end_date=request.end_date, parent=parent).record)
                audit["minkara_comments_raw"] += 1
        except (ExternalServiceError, ValueError, TypeError) as error:
            wrapped = error if isinstance(error, ExternalServiceError) else ExternalServiceError(
                ErrorType.MALFORMED_RESPONSE, "Minkara comments could not be parsed"
            )
            errors.append(wrapped); audit["sub_sources"]["minkara_comment"] = "partial"
