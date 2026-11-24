"""Antweiler & Frank (2004) bullishness / agreement from post-level scores."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


def _score_of(row: Mapping[str, Any], score_key: str, fallback_key: str) -> float:
    raw = row.get(score_key)
    if raw is None or raw == "":
        raw = row.get(fallback_key, 0.0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def classify_bull_bear(
    rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float = 0.05,
    score_key: str = "ai_score",
    fallback_key: str = "keyword_score",
) -> Tuple[int, int, int]:
    """Return (n_bull, n_bear, n_neutral) using signed score thresholds."""
    n_bull = n_bear = n_neu = 0
    tau = abs(float(threshold))
    for row in rows:
        s = _score_of(row, score_key, fallback_key)
        if s > tau:
            n_bull += 1
        elif s < -tau:
            n_bear += 1
        else:
            n_neu += 1
    return n_bull, n_bear, n_neu


def antweiler_bullishness(n_bull: int, n_bear: int) -> float:
    """B = ln((1+B)/(1+S)) as in Antweiler & Frank (JF 2004)."""
    return math.log((1.0 + max(0, int(n_bull))) / (1.0 + max(0, int(n_bear))))


def antweiler_agreement(n_bull: int, n_bear: int) -> float:
    """Agreement = 1 - sqrt(1 - ((B-S)/(B+S))^2); 0 if no directional posts."""
    b = max(0, int(n_bull))
    s = max(0, int(n_bear))
    total = b + s
    if total <= 0:
        return 0.0
    ratio = (b - s) / total
    inner = max(0.0, 1.0 - ratio * ratio)
    return 1.0 - math.sqrt(inner)


def attention_m(n_posts: int) -> float:
    """M = ln(1+N) message-volume proxy."""
    return math.log(1.0 + max(0, int(n_posts)))


def bullishness_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float = 0.05,
    score_key: str = "ai_score",
    fallback_key: str = "keyword_score",
) -> Dict[str, float]:
    n_bull, n_bear, n_neu = classify_bull_bear(
        rows, threshold=threshold, score_key=score_key, fallback_key=fallback_key
    )
    n_posts = len(rows)
    return {
        "bullishness": antweiler_bullishness(n_bull, n_bear),
        "agreement": antweiler_agreement(n_bull, n_bear),
        "attention_m": attention_m(n_posts),
        "n_posts": float(n_posts),
        "n_bull": float(n_bull),
        "n_bear": float(n_bear),
        "n_neutral": float(n_neu),
    }


def aggregate_bullishness(
    groups: Iterable[Sequence[Mapping[str, Any]]],
    **kwargs: Any,
) -> list[Dict[str, float]]:
    return [bullishness_from_rows(rows, **kwargs) for rows in groups]
