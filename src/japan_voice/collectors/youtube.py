"""Official YouTube Data API v3 collector for videos and top-level comments."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from pydantic import ValidationError

from japan_voice.config.settings import Settings, get_secret
from japan_voice.domain.enums import (
    CollectorStatus,
    ContentGroup,
    ContentType,
    EntityMatch,
    ScopeDecision,
    Source,
)
from japan_voice.domain.records import ContentRecord
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.errors import ErrorType, ExternalServiceError
from japan_voice.infrastructure.http import HttpClient
from japan_voice.infrastructure.logging import StructuredLogger
from japan_voice.processing.dates import jst_bounds
from japan_voice.processing.deduplicate import deduplicate
from japan_voice.processing.guardrails import evaluate_record
from .base import CollectorResult


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "YouTube timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "YouTube timestamp is invalid") from error
    if parsed.tzinfo is None:
        raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "YouTube timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def _items(payload: Mapping[str, Any], context: str) -> List[Mapping[str, Any]]:
    value = payload.get("items")
    if not isinstance(value, list):
        raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, f"YouTube {context} response has no items list")
    if not all(isinstance(item, dict) for item in value):
        raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, f"YouTube {context} items are malformed")
    return value


class YouTubeCollector:
    source = Source.YOUTUBE

    def __init__(
        self,
        *,
        http: HttpClient,
        settings: Settings,
        api_key: Optional[str] = None,
        logger: Optional[StructuredLogger] = None,
    ) -> None:
        self._http = http
        self._settings = settings
        self._api_key = api_key if api_key is not None else get_secret("YOUTUBE_API_KEY")
        self._logger = logger or StructuredLogger()

    def collect(self, request: SearchRequest, queries: Sequence[str]) -> CollectorResult:
        run_id = uuid4().hex
        started = time.monotonic()
        self._logger.event(run_id=run_id, source=self.source, event="collector_started")
        if not self._api_key:
            error = ExternalServiceError(
                ErrorType.AUTHENTICATION_ERROR,
                "YOUTUBE_API_KEY is not configured",
            )
            return self._failed(run_id, started, error)

        api_calls = 0
        search_api_calls = 0
        metadata_api_calls = 0
        comment_api_calls = 0
        errors: List[ExternalServiceError] = []
        try:
            video_ids, search_calls, search_errors = self._search(request, queries)
            api_calls += search_calls
            search_api_calls += search_calls
            errors.extend(search_errors)
            if not video_ids:
                if errors:
                    return self._failed(run_id, started, errors[0], api_calls=api_calls)
                error = ExternalServiceError(ErrorType.NO_DATA, "No YouTube videos found")
                return self._failed(run_id, started, error, api_calls=api_calls)

            videos, video_calls = self._video_records(request, video_ids)
            api_calls += video_calls
            metadata_api_calls += video_calls
            records: List[ContentRecord] = list(videos)
            video_audit: Dict[str, Dict[str, Any]] = {
                video.id: {
                    "video_id": video.native_id,
                    "video_title": video.title,
                    "video_published_at": video.published_at.isoformat() if video.published_at else None,
                    "displayed_comment_count": video.raw_metadata.get("displayed_comment_count"),
                    "raw_comments_collected": 0,
                    "comments_after_dedup": 0,
                    "collection_stop_reason": "not_eligible",
                } for video in videos
            }

            for video in videos:
                if not (
                    video.entity_match is EntityMatch.TARGET
                    and video.scope_decision is ScopeDecision.INCLUDE
                ):
                    continue
                try:
                    comments, comment_calls, comment_audit = self._comment_records(request, video)
                    api_calls += comment_calls
                    comment_api_calls += comment_calls
                    records.extend(comments)
                    video_audit[video.id].update(comment_audit)
                except ExternalServiceError as error:
                    api_calls += 1
                    comment_api_calls += 1
                    if error.details.get("reason") == "commentsDisabled":
                        video_audit[video.id]["collection_stop_reason"] = "comments_disabled"
                        continue
                    video_audit[video.id]["collection_stop_reason"] = "collection_error"
                    errors.append(error)

            records, duplicates = deduplicate(records)
            for video in videos:
                video_audit[video.id]["comments_after_dedup"] = sum(
                    record.parent_id == video.id and not record.duplicate_of
                    and record.eligible_for_analysis for record in records
                )
            metadata = {
                "run_id": run_id,
                "api_calls": api_calls,
                "search_api_calls": search_api_calls,
                "metadata_api_calls": metadata_api_calls,
                "comment_api_calls": comment_api_calls,
                "estimated_api_calls": search_api_calls + 1 + len(videos),
                "unique_videos": len(videos),
                "duplicates_marked": duplicates,
                "partial_errors": len(errors),
                "video_comment_audit": list(video_audit.values()),
            }
            duration = int((time.monotonic() - started) * 1000)
            if errors:
                result = CollectorResult.partial(
                    self.source, records, errors[0], metadata=metadata
                )
                event = "collector_partial"
            else:
                result = CollectorResult.success(self.source, records)
                result.metadata = metadata
                event = "collector_completed"
            self._logger.event(
                run_id=run_id,
                source=self.source,
                event=event,
                duration_ms=duration,
                records_collected=result.records_collected,
                error_type=result.error_type,
                metric_api_calls=api_calls,
            )
            return result
        except ExternalServiceError as error:
            return self._failed(run_id, started, error, api_calls=api_calls)
        except (KeyError, TypeError, ValidationError) as error:
            malformed = ExternalServiceError(
                ErrorType.MALFORMED_RESPONSE,
                "YouTube response could not be normalized",
            )
            return self._failed(run_id, started, malformed, api_calls=api_calls)
        except Exception:
            unknown = ExternalServiceError(ErrorType.UNKNOWN_ERROR, "Unexpected YouTube collector error")
            return self._failed(run_id, started, unknown, api_calls=api_calls)

    def _failed(
        self,
        run_id: str,
        started: float,
        error: ExternalServiceError,
        *,
        api_calls: int = 0,
    ) -> CollectorResult:
        result = CollectorResult(
            source=self.source,
            status=CollectorStatus.FAILED,
            error_type=error.error_type,
            error_message=str(error),
            metadata={"run_id": run_id, "api_calls": api_calls},
        )
        self._logger.event(
            run_id=run_id,
            source=self.source,
            event="collector_failed",
            duration_ms=int((time.monotonic() - started) * 1000),
            records_collected=0,
            error_type=error.error_type,
            metric_api_calls=api_calls,
        )
        return result

    def _search(
        self, request: SearchRequest, queries: Sequence[str]
    ) -> Tuple[List[str], int, List[ExternalServiceError]]:
        max_videos = min(request.max_results, self._settings.youtube_max_videos)
        windows = self._date_windows(request.start_date, request.end_date)
        seen = set()
        video_ids: List[str] = []
        errors: List[ExternalServiceError] = []
        calls = 0
        bounded_queries = list(queries[: self._settings.max_query_variants_per_source])
        # For long ranges, reserve capacity for every time window so a relevance-
        # sorted response from the newest period cannot consume the whole limit.
        multi_window = len(windows) > 1
        if multi_window and max_videos < len(windows):
            indexes = [round(i * (len(windows) - 1) / max(1, max_videos - 1)) for i in range(max_videos)]
            windows = [windows[index] for index in dict.fromkeys(indexes)]
        searches = [
            (bounded_queries[index % len(bounded_queries)], window)
            for index, window in enumerate(windows)
        ] if multi_window and bounded_queries else [
            (query, windows[0]) for query in bounded_queries
        ]
        base_quota, remainder = divmod(max_videos, max(1, len(searches)))
        for search_index, (query, (start_utc, end_utc)) in enumerate(searches):
            window_quota = max(1, base_quota + (1 if search_index < remainder else 0))
            try:
                page_token: Optional[str] = None
                collected_for_search = 0
                while collected_for_search < window_quota and len(video_ids) < max_videos:
                    params: Dict[str, Any] = {
                        "key": self._api_key,
                        "part": "snippet",
                        "type": "video",
                        "q": query,
                        "relevanceLanguage": "ja",
                        "regionCode": "JP",
                        "order": "date",
                        "publishedAfter": start_utc.isoformat().replace("+00:00", "Z"),
                        "publishedBefore": end_utc.isoformat().replace("+00:00", "Z"),
                        "maxResults": min(50, window_quota - collected_for_search),
                    }
                    if page_token:
                        params["pageToken"] = page_token
                    payload = self._http.get_json(f"{YOUTUBE_API_BASE}/search", params=params)
                    calls += 1
                    page_items = _items(payload, "search")
                    collected_for_search += len(page_items)
                    for item in page_items:
                        video_id = item.get("id", {}).get("videoId")
                        if isinstance(video_id, str) and video_id and video_id not in seen:
                            seen.add(video_id)
                            video_ids.append(video_id)
                            if len(video_ids) >= max_videos:
                                break
                    page_token = payload.get("nextPageToken")
                    if not page_token or not page_items:
                        break
            except ExternalServiceError as error:
                errors.append(error)
                if error.code in {
                    ErrorType.AUTHENTICATION_ERROR,
                    ErrorType.PERMISSION_ERROR,
                    ErrorType.QUOTA_EXCEEDED,
                    ErrorType.RATE_LIMITED,
                }:
                    break
        return video_ids[:max_videos], calls, errors

    def _date_windows(self, start: date, end: date) -> List[Tuple[datetime, datetime]]:
        """Return bounded oldest-to-newest JST calendar-month search windows."""
        month_starts: List[date] = []
        cursor = start
        while cursor <= end:
            month_starts.append(cursor)
            cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        max_windows = self._settings.youtube_max_search_windows
        if len(month_starts) <= max_windows:
            ranges = []
            for index, window_start in enumerate(month_starts):
                next_start = month_starts[index + 1] if index + 1 < len(month_starts) else end + timedelta(days=1)
                window_end = min(end, next_start - timedelta(days=1))
                ranges.append(jst_bounds(window_start, window_end))
            return ranges
        # Extremely long ranges remain bounded while retaining full coverage.
        total_days = (end - start).days + 1
        ranges = []
        for index in range(max_windows):
            window_start = start + timedelta(days=(total_days * index) // max_windows)
            next_start = start + timedelta(days=(total_days * (index + 1)) // max_windows)
            ranges.append(jst_bounds(window_start, next_start - timedelta(days=1)))
        return ranges

    def _video_records(
        self, request: SearchRequest, video_ids: Sequence[str]
    ) -> Tuple[List[ContentRecord], int]:
        records: List[ContentRecord] = []
        calls = 0
        for offset in range(0, len(video_ids), 50):
            batch_ids = video_ids[offset:offset + 50]
            payload = self._http.get_json(
                f"{YOUTUBE_API_BASE}/videos",
                params={
                    "key": self._api_key,
                    "part": "snippet,statistics",
                    "id": ",".join(batch_ids),
                    "maxResults": len(batch_ids),
                },
            )
            calls += 1
            for item in _items(payload, "videos"):
                video_id = item.get("id")
                snippet = item.get("snippet")
                if not isinstance(video_id, str) or not isinstance(snippet, dict):
                    raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "YouTube video item is malformed")
                record = ContentRecord(
                    id=f"youtube:video:{video_id}", source=self.source, provider="YouTube",
                    native_id=video_id, content_type=ContentType.VIDEO,
                    content_group=ContentGroup.MARKET_CONTENT, keyword=request.keyword,
                    title=str(snippet.get("title") or ""), content=str(snippet.get("description") or ""),
                    author=str(snippet.get("channelTitle")) if snippet.get("channelTitle") else None,
                    published_at=_parse_datetime(snippet.get("publishedAt")),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    raw_metadata={"channel_id": snippet.get("channelId"),
                        "displayed_comment_count": self._displayed_comment_count(item)},
                )
                records.append(evaluate_record(record, start_date=request.start_date,
                    end_date=request.end_date).record)
        return records, calls

    @staticmethod
    def _displayed_comment_count(item: Mapping[str, Any]) -> Optional[int]:
        value = item.get("statistics", {}).get("commentCount")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _comment_records(
        self, request: SearchRequest, parent: ContentRecord
    ) -> Tuple[List[ContentRecord], int, Dict[str, Any]]:
        video_id = parent.native_id
        records: List[ContentRecord] = []
        calls = 0
        page_token: Optional[str] = None
        stop_reason = "unknown"
        while calls < self._settings.youtube_comment_max_pages:
            remaining = self._settings.youtube_comment_safety_limit - len(records)
            if remaining <= 0:
                stop_reason = "technical_safety_limit"
                break
            params: Dict[str, Any] = {
                "key": self._api_key, "part": "snippet", "videoId": video_id,
                "order": "time", "textFormat": "plainText", "maxResults": min(100, remaining),
            }
            if page_token:
                params["pageToken"] = page_token
            payload = self._http.get_json(f"{YOUTUBE_API_BASE}/commentThreads", params=params)
            calls += 1
            page_items = _items(payload, "comments")
            for item in page_items:
                comment_id = item.get("id")
                top = item.get("snippet", {}).get("topLevelComment", {})
                snippet = top.get("snippet") if isinstance(top, dict) else None
                native_comment_id = top.get("id") if isinstance(top, dict) else None
                comment_id = native_comment_id or comment_id
                if not isinstance(comment_id, str) or not isinstance(snippet, dict):
                    raise ExternalServiceError(ErrorType.MALFORMED_RESPONSE, "YouTube comment item is malformed")
                text = snippet.get("textDisplay") or snippet.get("textOriginal")
                if not isinstance(text, str) or not text.strip():
                    continue
                record = ContentRecord(
                    id=f"youtube:comment:{comment_id}", source=self.source, provider="YouTube",
                    native_id=comment_id, parent_id=parent.id, content_type=ContentType.COMMENT,
                    content_group=ContentGroup.CONSUMER_VOICE, keyword=request.keyword,
                    title=parent.title, content=text,
                    author=str(snippet.get("authorDisplayName")) if snippet.get("authorDisplayName") else None,
                    published_at=_parse_datetime(snippet.get("publishedAt")),
                    url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                    parent_url=parent.url, engagement_count=int(snippet.get("likeCount", 0)),
                    is_comment=True,
                )
                records.append(evaluate_record(record, start_date=request.start_date,
                    end_date=request.end_date, parent=parent).record)
                if len(records) >= self._settings.youtube_comment_safety_limit:
                    break
            page_token = payload.get("nextPageToken")
            if not page_token:
                stop_reason = "no_comments" if calls == 1 and not page_items else "pagination_exhausted"
                break
        else:
            stop_reason = "technical_safety_limit"
        return records, calls, {
            "raw_comments_collected": len(records),
            "collection_stop_reason": stop_reason,
        }
