"""Lightweight trade-date normalization (no heavy tz deps beyond stdlib + pandas)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo

import pandas as pd

DateLike = Union[str, date, datetime, pd.Timestamp, None]


def normalize_trade_date(
    value: DateLike,
    *,
    default_tz: str = "Asia/Shanghai",
    fallback: Optional[date] = None,
) -> Optional[date]:
    """Parse messy trade_date strings into a calendar ``date`` in ``default_tz``.

    Handles ISO dates, ``YYYY/MM/DD``, pandas timestamps, and naive datetimes
    (interpreted as local wall time in ``default_tz``).
    """
    if value is None or value == "":
        return fallback
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(ZoneInfo(default_tz)).date()
        return value.date()
    try:
        ts = pd.Timestamp(value)
        if pd.isna(ts):
            return fallback
        if ts.tzinfo is not None:
            return ts.tz_convert(default_tz).date()
        return ts.date()
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text:
        return fallback
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        ts = pd.to_datetime(text, errors="coerce", utc=False)
        if pd.isna(ts):
            return fallback
        if getattr(ts, "tzinfo", None) is not None:
            return ts.tz_convert(default_tz).date()
        return ts.date()
    except (TypeError, ValueError):
        return fallback


def utc_now_iso() -> str:
    """UTC timestamp string for logs / exports."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
