"""Pooled logistic regression for up/down prediction (thesis Logit)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


@dataclass
class LogitResult:
    measure: str
    horizon: int
    coef: float
    intercept: float
    accuracy: float
    auc: float
    n_obs: int
    pos_rate: float


def _sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-z))


def _fit_logit(
    X: np.ndarray,
    y: np.ndarray,
    *,
    max_iter: int = 100,
    tol: float = 1e-6,
    l2: float = 1e-4,
) -> np.ndarray:
    """Newton / IRLS logistic regression. X includes intercept column."""
    n, k = X.shape
    beta = np.zeros(k, dtype=float)
    for _ in range(max_iter):
        p = _sigmoid(X @ beta)
        w = p * (1.0 - p)
        w = np.clip(w, 1e-6, None)
        # Gradient and Hessian
        grad = X.T @ (y - p) - l2 * beta
        # Weighted X'WX
        Xw = X * w[:, None]
        hess = X.T @ Xw + l2 * np.eye(k)
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hess, grad, rcond=None)[0]
        beta = beta + step
        if float(np.max(np.abs(step))) < tol:
            break
    return beta


def _auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Mann–Whitney AUC without sklearn."""
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    pos = s[y == 1]
    neg = s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    # Rank-based
    order = np.argsort(s)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(s) + 1, dtype=float)
    # Average ranks for ties
    # (simple version; fine for smoke/thesis prototype)
    sum_ranks_pos = float(np.sum(ranks[y == 1]))
    auc = (sum_ranks_pos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))
    return float(auc)


def run_direction_logit(
    panel: pd.DataFrame,
    *,
    measure_col: str,
    horizon: int = 1,
    date_col: str = "trade_date",
    ret_prefix: str = "ret_",
    control_cols: Optional[Sequence[str]] = None,
) -> LogitResult:
    work = panel.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    ret_col = f"{ret_prefix}{int(horizon)}d"
    if ret_col not in work.columns:
        raise ValueError(f"missing return column {ret_col}")
    controls = [c for c in (control_cols or []) if c in work.columns]
    cols = [measure_col, ret_col, *controls]
    sub = work[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if sub.empty:
        return LogitResult(
            measure=measure_col,
            horizon=int(horizon),
            coef=float("nan"),
            intercept=float("nan"),
            accuracy=float("nan"),
            auc=float("nan"),
            n_obs=0,
            pos_rate=float("nan"),
        )
    y = (sub[ret_col].to_numpy(dtype=float) > 0.0).astype(float)
    parts = [np.ones(len(sub)), sub[measure_col].to_numpy(dtype=float)]
    for c in controls:
        parts.append(sub[c].to_numpy(dtype=float))
    X = np.column_stack(parts)
    beta = _fit_logit(X, y)
    scores = _sigmoid(X @ beta)
    pred = (scores >= 0.5).astype(float)
    acc = float(np.mean(pred == y)) if len(y) else float("nan")
    return LogitResult(
        measure=measure_col,
        horizon=int(horizon),
        coef=float(beta[1]),
        intercept=float(beta[0]),
        accuracy=acc,
        auc=_auc(y, scores),
        n_obs=int(len(sub)),
        pos_rate=float(np.mean(y)),
    )


def run_direction_logit_grid(
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
            res = run_direction_logit(panel, measure_col=m, horizon=int(h), **kwargs)  # type: ignore[arg-type]
            rows.append(
                {
                    "measure": res.measure,
                    "horizon": res.horizon,
                    "coef": res.coef,
                    "intercept": res.intercept,
                    "accuracy": res.accuracy,
                    "auc": res.auc,
                    "n_obs": res.n_obs,
                    "pos_rate": res.pos_rate,
                }
            )
    return pd.DataFrame(rows)
