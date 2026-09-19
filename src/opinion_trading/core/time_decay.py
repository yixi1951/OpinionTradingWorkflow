"""Recency weighting for raw posts (newer posts count more toward platform score)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional


def parse_post_datetime(post_time: str, trade_date: date) -> Optional[datetime]:
    """Best-effort parse; returns None if unknown."""
    text = str(post_time or "").strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
    ):
        try:
            dt = datetime.strptime(text[:19], fmt)
            return dt
        except ValueError:
            continue
    m = re.search(r"20\d{2}-\d{1,2}-\d{1,2}", text)
    if m:
        try:
            return datetime.strptime(m.group(0), "%Y-%m-%d")
        except ValueError:
            pass
    m2 = re.fullmatch(r"\d{2}-\d{2}", text)
    if m2:
        try:
            return datetime.strptime(f"{trade_date.year}-{text}", "%Y-%m-%d")
        except ValueError:
            pass
    return None


def recency_weight(
    post_dt: Optional[datetime],
    *,
    as_of: datetime,
    half_life_hours: float = 24.0,
) -> float:
    """Exponential decay: weight 1.0 at as_of, 0.5 at half_life_hours ago."""
    if post_dt is None or half_life_hours <= 0:
        return 1.0
    age_h = max(0.0, (as_of - post_dt).total_seconds() / 3600.0)
    import math

    return math.exp(-0.693147 * age_h / half_life_hours)


def weighted_mean_scores(
    rows: List[Dict[str, Any]],
    trade_date: date,
    *,
    half_life_hours: float = 24.0,
    score_key: str = "ai_score",
    fallback_key: str = "keyword_score",
) -> float:
    if not rows:
        return 0.0
    as_of = datetime.combine(trade_date, datetime.max.time())
    num = 0.0
    den = 0.0
    for row in rows:
        sc = row.get(score_key)
        if sc is None or sc == "":
            sc = row.get(fallback_key, 0.0)
        try:
            val = float(sc)
        except (TypeError, ValueError):
            val = 0.0
        post_dt = parse_post_datetime(str(row.get("post_time", "")), trade_date)
        w = recency_weight(post_dt, as_of=as_of, half_life_hours=half_life_hours)
        try:
            from opinion_trading.core.signal_weights import combined_post_weight

            auth_w = float(combined_post_weight(row))
        except Exception:
            try:
                auth_w = float(row.get("authority_weight", 1.0) or 1.0)
            except (TypeError, ValueError):
                auth_w = 1.0
        # Down-weight non-entity / noise content when semantic fields exist
        if "entity_matched" in row and not bool(row.get("entity_matched")):
            auth_w *= 0.5
        if str(row.get("content_kind", "")) == "noise":
            auth_w *= 0.35
        w *= max(0.1, auth_w)
        num += val * w
        den += w
    if den <= 0:
        return sum(float(r.get(fallback_key, 0) or 0) for r in rows) / len(rows)
    return max(-1.0, min(1.0, num / den))
