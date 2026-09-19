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
        per_symbol=bool(block.get("per_symbol", False)),
        adaptive=bool(block.get("adaptive", False)),
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


def _adaptive_percentiles(
    lower_pct: float, upper_pct: float, n: int
) -> tuple[float, float]:
    """Widen clip band when sample size is small (research guard)."""
    if not n or n >= 30:
        return lower_pct, upper_pct
    widen = min(5.0, max(0.0, (30 - n) * 0.15))
    return max(0.0, lower_pct - widen), min(100.0, upper_pct + widen)


def _winsorize_row_scores(
    row: Dict[str, Any],
    lo: float,
    hi: float,
    score_keys: tuple[str, ...],
) -> Dict[str, Any]:
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
    return new_row


def winsorize_raw_rows(
    rows: List[Dict[str, Any]],
    *,
    config: SentimentWinsorizeConfig,
    score_keys: tuple[str, ...] = ("ai_score", "keyword_score"),
) -> List[Dict[str, Any]]:
    """Apply winsorization to row-level sentiment fields (mutates copies)."""
    if not config.enabled or not rows:
        return rows

    per_symbol = bool(getattr(config, "per_symbol", False))
    adaptive = bool(getattr(config, "adaptive", False))

    if per_symbol:
        by_sym: Dict[str, List[Dict[str, Any]]] = {}
        order: List[tuple[str, int]] = []
        for idx, row in enumerate(rows):
            sym = str(row.get("symbol") or "__all__")
            by_sym.setdefault(sym, []).append(row)
            order.append((sym, len(by_sym[sym]) - 1))
        clipped: Dict[str, List[Dict[str, Any]]] = {}
        for sym, sym_rows in by_sym.items():
            pool: List[float] = []
            for row in sym_rows:
                for key in score_keys:
                    val = row.get(key)
                    if val is None or val == "":
                        continue
                    try:
                        pool.append(float(val))
                    except (TypeError, ValueError):
                        continue
            if len(pool) < 2:
                clipped[sym] = [dict(r) for r in sym_rows]
                continue
            lo_pct, hi_pct = config.lower_pct, config.upper_pct
            if adaptive:
                lo_pct, hi_pct = _adaptive_percentiles(
                    lo_pct, hi_pct, len(pool)
                )
            lo, hi = _clip_bounds(pool, lo_pct, hi_pct)
            clipped[sym] = [
                _winsorize_row_scores(r, lo, hi, score_keys) for r in sym_rows
            ]
        out: List[Dict[str, Any]] = []
        counters: Dict[str, int] = {}
        for sym, _ in order:
            i = counters.get(sym, 0)
            out.append(clipped[sym][i])
            counters[sym] = i + 1
        return out

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
    lo_pct, hi_pct = config.lower_pct, config.upper_pct
    if adaptive:
        lo_pct, hi_pct = _adaptive_percentiles(lo_pct, hi_pct, len(pool))
    lo, hi = _clip_bounds(pool, lo_pct, hi_pct)
    return [_winsorize_row_scores(r, lo, hi, score_keys) for r in rows]
