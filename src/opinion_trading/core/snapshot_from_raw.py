"""Build OpinionSnapshot list from cached raw CSV rows (fast-daily replay)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from opinion_trading.core.models import OpinionSnapshot
from opinion_trading.core.time_decay import weighted_mean_scores


def snapshots_from_raw_rows(
    raw_rows: List[Dict[str, Any]],
    trade_date: date,
    *,
    recency_enabled: bool = True,
    half_life_hours: float = 24.0,
) -> List[OpinionSnapshot]:
    """Aggregate per (platform, symbol) using ai_score or keyword_score."""
    buckets: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        td = str(row.get("trade_date", ""))[:10]
        if td and td != trade_date.isoformat():
            continue
        platform = str(row.get("platform", "unknown"))
        symbol = str(row.get("symbol", ""))
        if not symbol:
            continue
        buckets[(platform, symbol)].append(dict(row))

    out: List[OpinionSnapshot] = []
    now = datetime.now()
    for (platform, symbol), rows in buckets.items():
        # Prefer non-noise / relevant rows for aggregation
        usable = [
            r
            for r in rows
            if not bool(r.get("is_noise"))
            and r.get("ai_relevant", True) is not False
            and str(r.get("capture_status", "success")) not in {"fail"}
        ]
        if not usable:
            usable = [
                r
                for r in rows
                if str(r.get("capture_status", "")) not in {"fail", "fallback"}
            ] or rows
        if recency_enabled:
            avg = weighted_mean_scores(
                usable,
                trade_date,
                half_life_hours=half_life_hours,
            )
        else:
            scores: List[float] = []
            for row in usable:
                score = row.get("ai_score")
                if score is None or score == "":
                    score = row.get("keyword_score", 0.0)
                try:
                    scores.append(float(score))
                except (TypeError, ValueError):
                    scores.append(0.0)
            avg = sum(scores) / len(scores) if scores else 0.0
            avg = max(-1.0, min(1.0, avg))
        out.append(
            OpinionSnapshot(
                timestamp=now,
                trade_date=trade_date,
                platform=platform,
                symbol=symbol,
                sentiment_score=avg,
                post_count=len(usable),
                source="raw_csv_replay",
            )
        )
    return out