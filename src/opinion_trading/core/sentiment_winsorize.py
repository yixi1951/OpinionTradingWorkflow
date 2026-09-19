"""Percentile clipping for sentiment scores (optional quality / scoring guard)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from opinion_trading.core.models import SentimentWinsorizeConfig


def load_sentiment_winsorize_config(
    raw: Optional[Dict[str, Any]] = None,
) -> SentimentWinsorizeConfig:
    import os

    qual = (raw or {}).get("quality", {}) or {}
    block = qual.get("sentiment_winsorize", {}) or {}
    env_on = os.environ.get("SENTIMENT_WINSORIZE", "").strip().lower()
    enabled = bool(block.get("enabled", False))
    if env_on in ("1", "true", "yes", "on"):
        enabled = True
    elif env_on in ("0", "false", "no", "off"):
        enabled = False
    return SentimentWinsorizeConfig(
        enabled=enabled,
        lower_pct=float(block.get("lower_pct", 1.0)),
        upper_pct=float(block.get("upper_pct", 99.0)),
    )


def _clip_bounds(values: Sequence[float], lower_pct: float, upper_pct: float) -> tuple[float, float]:
    if not values:
        return -1.0, 1.0
    arr = np.asarray(list(values), dtype=float)
    lo = float(np.nanpercentile(arr, lower_pct))
    hi = float(np.nanpercentile(arr, upper_pct))
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi


def winsorize_scores(
    scores: Iterable[float],
    *,
    lower_pct: float = 1.0,
    upper_pct: float = 99.0,
) -> List[float]:
    """Clip each score to the batch [lower_pct, upper_pct] percentiles."""
    vals = [float(s) for s in scores]
    if len(vals) < 2:
        return [max(-1.0, min(1.0, v)) for v in vals]
    lo, hi = _clip_bounds(vals, lower_pct, upper_pct)
    return [max(lo, min(hi, v)) for v in vals]


def winsorize_raw_rows(
    rows: List[Dict[str, Any]],
    *,
    config: SentimentWinsorizeConfig,
    score_keys: tuple[str, ...] = ("ai_score", "keyword_score"),
) -> List[Dict[str, Any]]:
    """Apply winsorization to row-level sentiment fields (mutates copies)."""
    if not config.enabled or not rows:
        return rows
    pool: List[float] = []
    for row in rows:
        for key in score_keys:
            val = row.get(key)
            if val is None or val == "":
                continue
            try:
                pool.append(float(val))
            except (TypeError, ValueError):
                continue
    if len(pool) < 2:
        return rows
    lo, hi = _clip_bounds(pool, config.lower_pct, config.upper_pct)
    out: List[Dict[str, Any]] = []
    for row in rows:
        new_row = dict(row)
        for key in score_keys:
            val = new_row.get(key)
            if val is None or val == "":
                continue
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            if fval < lo or fval > hi:
                new_row[key] = max(lo, min(hi, fval))
        out.append(new_row)
    return out
