"""Factor validation helpers: IC, ICIR, annualized excess return."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd


def _safe_corr(x: Sequence[float], y: Sequence[float], method: str = "spearman") -> float:
    if len(x) < 3 or len(y) < 3 or len(x) != len(y):
        return 0.0
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float)
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 3:
        return 0.0
    a, b = a[mask], b[mask]
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return 0.0
    if method == "pearson":
        return float(np.corrcoef(a, b)[0, 1])
    # rank (Spearman) IC
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def compute_factor_ic(
    factor_values: Sequence[float],
    forward_returns: Sequence[float],
    *,
    method: str = "spearman",
) -> float:
    """Cross-sectional / pooled IC between factor and forward returns."""
    return _safe_corr(factor_values, forward_returns, method=method)


def compute_icir(period_ics: Iterable[float]) -> float:
    """IC Information Ratio = mean(IC) / std(IC)."""
    vals = [float(x) for x in period_ics if x is not None and math.isfinite(float(x))]
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    var = sum((x - mean) ** 2 for x in vals) / len(vals)
    std = math.sqrt(var)
    return mean / (std + 1e-12)


def annualize_return(mean_daily: float, periods: int = 252) -> float:
    """Annualize a mean daily return. Accepts scalar or length-1 array-like."""
    try:
        md = float(np.asarray(mean_daily, dtype=float).reshape(-1)[0])
    except (TypeError, ValueError, IndexError):
        return 0.0
    if not math.isfinite(md):
        return 0.0
    return float((1.0 + md) ** periods - 1.0) if md > -1.0 else -1.0


def compute_excess_return(
    strategy_returns: Sequence[float],
    benchmark_returns: Sequence[float],
) -> Dict[str, float]:
    """Annualized excess return and tracking stats vs benchmark."""
    s = np.asarray(list(strategy_returns), dtype=float)
    b = np.asarray(list(benchmark_returns), dtype=float)
    n = min(len(s), len(b))
    if n == 0:
        return {
            "excess_return_ann": 0.0,
            "strategy_ann": 0.0,
            "benchmark_ann": 0.0,
            "tracking_error": 0.0,
            "information_ratio": 0.0,
        }
    s, b = s[:n], b[:n]
    excess = s - b
    mean_s = float(np.nanmean(s))
    mean_b = float(np.nanmean(b))
    mean_x = float(np.nanmean(excess))
    std_x = float(np.nanstd(excess))
    strategy_ann = annualize_return(mean_s)
    benchmark_ann = annualize_return(mean_b)
    excess_ann = strategy_ann - benchmark_ann
    te = std_x * math.sqrt(252) if n > 1 else 0.0
    ir = (mean_x * math.sqrt(252)) / (std_x + 1e-12) if n > 1 else 0.0
    return {
        "excess_return_ann": float(excess_ann),
        "strategy_ann": float(strategy_ann),
        "benchmark_ann": float(benchmark_ann),
        "tracking_error": float(te),
        "information_ratio": float(ir),
    }


def rolling_date_ic(
    df: pd.DataFrame,
    *,
    date_col: str = "trade_date",
    factor_col: str = "factor",
    return_col: str = "next_return",
    method: str = "spearman",
) -> Tuple[float, float, List[float]]:
    """Compute mean IC / ICIR across trade dates (cross-section per day when possible)."""
    if df.empty or factor_col not in df.columns or return_col not in df.columns:
        return 0.0, 0.0, []
    work = df.dropna(subset=[factor_col, return_col]).copy()
    if work.empty:
        return 0.0, 0.0, []
    ics: List[float] = []
    if date_col in work.columns and work[date_col].nunique() >= 2:
        for _, group in work.groupby(date_col):
            if len(group) < 3:
                # too few names — still record pooled pair contribution via skip
                continue
            ics.append(
                compute_factor_ic(
                    group[factor_col].tolist(),
                    group[return_col].tolist(),
                    method=method,
                )
            )
    if not ics:
        # pooled IC fallback (student-scale universe often <3 names/day)
        pooled = compute_factor_ic(
            work[factor_col].tolist(), work[return_col].tolist(), method=method
        )
        return pooled, 0.0, [pooled]
    mean_ic = float(sum(ics) / len(ics))
    return mean_ic, compute_icir(ics), ics
