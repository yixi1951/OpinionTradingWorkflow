"""Fama–MacBeth cross-sectional regressions for thesis horizons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


@dataclass
class FMResult:
    measure: str
    horizon: int
    coef_mean: float
    coef_se: float
    t_stat: float
    n_days: int
    n_obs: int
    avg_r2: float


def _newey_west_se(series: np.ndarray, lags: int = 3) -> float:
    """HAC SE for the mean of a coefficient time series."""
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n <= 1:
        return float("nan")
    mean = float(np.mean(x))
    resid = x - mean
    gamma0 = float(np.dot(resid, resid) / n)
    var = gamma0
    L = max(0, min(int(lags), n - 1))
    for lag in range(1, L + 1):
        w = 1.0 - lag / (L + 1.0)
        gamma = float(np.dot(resid[lag:], resid[:-lag]) / n)
        var += 2.0 * w * gamma
    return float(np.sqrt(max(var, 0.0) / n))


def _day_ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, float]:
    """Return beta and R^2 for y = X b (X already includes intercept column)."""
    if len(y) < X.shape[1] + 1:
        return np.full(X.shape[1], np.nan), float("nan")
    try:
        beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    except Exception:
        return np.full(X.shape[1], np.nan), float("nan")
    fitted = X @ beta
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-18 else float("nan")
    return beta, r2


def run_fama_macbeth(
    panel: pd.DataFrame,
    *,
    measure_col: str,
    horizon: int = 1,
    date_col: str = "trade_date",
    ret_prefix: str = "ret_",
    control_cols: Optional[Sequence[str]] = None,
    min_cross_section: int = 5,
    nw_lags: int = 3,
) -> FMResult:
    """Daily CS regression of ret_{h}d on measure (+ controls), then average betas."""
    work = panel.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    ret_col = f"{ret_prefix}{int(horizon)}d"
    if ret_col not in work.columns:
        raise ValueError(f"missing return column {ret_col}")
    controls = [c for c in (control_cols or []) if c in work.columns]

    day_betas: List[float] = []
    day_r2: List[float] = []
    n_obs = 0
    for _, g in work.groupby(date_col):
        cols = [measure_col, ret_col, *controls]
        sub = g[cols].apply(pd.to_numeric, errors="coerce").dropna()
        if len(sub) < max(min_cross_section, 2 + len(controls)):
            continue
        y = sub[ret_col].to_numpy(dtype=float)
        parts = [np.ones(len(sub)), sub[measure_col].to_numpy(dtype=float)]
        for c in controls:
            parts.append(sub[c].to_numpy(dtype=float))
        X = np.column_stack(parts)
        beta, r2 = _day_ols(y, X)
        if not np.isfinite(beta[1]):
            continue
        day_betas.append(float(beta[1]))
        if np.isfinite(r2):
            day_r2.append(float(r2))
        n_obs += len(sub)

    arr = np.asarray(day_betas, dtype=float)
    if len(arr) == 0:
        return FMResult(
            measure=measure_col,
            horizon=int(horizon),
            coef_mean=float("nan"),
            coef_se=float("nan"),
            t_stat=float("nan"),
            n_days=0,
            n_obs=0,
            avg_r2=float("nan"),
        )
    mean = float(np.mean(arr))
    se = _newey_west_se(arr, lags=nw_lags)
    t = mean / se if se and np.isfinite(se) and se > 0 else float("nan")
    return FMResult(
        measure=measure_col,
        horizon=int(horizon),
        coef_mean=mean,
        coef_se=float(se),
        t_stat=float(t),
        n_days=len(arr),
        n_obs=int(n_obs),
        avg_r2=float(np.mean(day_r2)) if day_r2 else float("nan"),
    )


def run_fama_macbeth_grid(
    panel: pd.DataFrame,
    measures: Sequence[str],
    horizons: Sequence[int] = (1, 3, 5),
    **kwargs: object,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for m in measures:
        if m not in panel.columns:
            continue
        for h in horizons:
            res = run_fama_macbeth(panel, measure_col=m, horizon=int(h), **kwargs)  # type: ignore[arg-type]
            rows.append(
                {
                    "measure": res.measure,
                    "horizon": res.horizon,
                    "coef_mean": res.coef_mean,
                    "coef_se": res.coef_se,
                    "t_stat": res.t_stat,
                    "n_days": res.n_days,
                    "n_obs": res.n_obs,
                    "avg_r2": res.avg_r2,
                }
            )
    return pd.DataFrame(rows)
