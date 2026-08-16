"""Inclusive JST date filtering with UTC-aware record timestamps."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from japan_voice.domain.enums import DateStatus


JST = ZoneInfo("Asia/Tokyo")
UTC = timezone.utc


def jst_bounds(start_date: date, end_date: date) -> Tuple[datetime, datetime]:
    """Return the half-open UTC interval covering inclusive JST dates."""
    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")
    start_jst = datetime.combine(start_date, time.min, tzinfo=JST)
    end_exclusive_jst = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=JST)
    return start_jst.astimezone(UTC), end_exclusive_jst.astimezone(UTC)


def evaluate_date(
    published_at: Optional[datetime], start_date: date, end_date: date
) -> Tuple[DateStatus, bool]:
    if published_at is None:
        return DateStatus.UNKNOWN, False
    if published_at.tzinfo is None or published_at.utcoffset() is None:
        return DateStatus.INVALID, False
    start_utc, end_utc = jst_bounds(start_date, end_date)
    instant = published_at.astimezone(UTC)
    return DateStatus.KNOWN, start_utc <= instant < end_utc
