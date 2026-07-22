"""Lightweight daily factor backtest: IC / IR / group excess / lead-lag vs HS300."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from opinion_trading.core.factor_metrics import (
    compute_excess_return,
    compute_factor_ic,
    compute_icir,
    rolling_date_ic,
)
from opinion_trading.core.log_utils import get_logger
from opinion_trading.core.metrics import compute_performance_metrics

logger = get_logger(__name__)


@dataclass
class FactorBacktestReport:
    horizons: Dict[int, Dict[str, float]] = field(default_factory=dict)
    group_excess: Dict[str, float] = field(default_factory=dict)
    vs_benchmark: Dict[str, float] = field(default_factory=dict)
    n_days: int = 0
    n_obs: int = 0


def _to_ak_symbol(symbol: str) -> str:
    s = str(symbol).upper().strip()
    if s.endswith(".SH"):
        return s.replace(".SH", "")
    if s.endswith(".SZ"):
        return s.replace(".SZ", "")
    return s


def fetch_hs300_benchmark(
    start: str,
    end: str,
    *,
    cache_csv: str = "data/reports/hs300_benchmark.csv",
) -> pd.DataFrame:
    """Fetch HS300 daily close via akshare; cache locally."""
    cache = Path(cache_csv)
    try:
        import akshare as ak  # type: ignore

        df = ak.stock_zh_index_daily(symbol="sh000300")
        df = df.rename(columns={"date": "date", "close": "close"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "close"])
        df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
        df = df[["date", "close"]].sort_values("date")
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache, index=False)
        return df
    except Exception as exc:
        logger.warning("HS300 fetch failed: %s", exc)
        if cache.exists():
            df = pd.read_csv(cache)
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df.dropna(subset=["date", "close"])
        # Synthetic flat benchmark for offline tests
        dates = pd.date_range(start, end, freq="B")
        return pd.DataFrame({"date": dates, "close": np.linspace(4000, 4100, len(dates))})


def attach_forward_returns(
    price_df: pd.DataFrame,
    horizons: Sequence[int] = (1, 3, 5),
) -> pd.DataFrame:
    """Add ret_{h}d forward returns per symbol."""
    df = price_df.copy()
    if "date" not in df.columns:
        raise ValueError("price_df needs date column")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "close"]).sort_values(["symbol", "date"])
    for h in horizons:
        df[f"ret_{h}d"] = df.groupby("symbol")["close"].shift(-h) / df["close"] - 1.0
    return df


def neutralize_factor(
    factor_df: pd.DataFrame,
    *,
    factor_col: str = "factor",
    date_col: str = "trade_date",
    industry_col: str = "industry",
    mcap_col: str = "log_mcap",
) -> pd.Series:
    """Cross-sectional residualize factor on industry dummies + log mcap (per day).

    If industry/mcap missing, demean within date only (partial neutralization).
    """
    work = factor_df.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    residuals = pd.Series(index=work.index, dtype=float)

    for _, group in work.groupby(date_col):
        y = group[factor_col].astype(float)
        if y.isna().all() or y.std(ddof=0) < 1e-12:
            residuals.loc[group.index] = 0.0
            continue
        X_parts = [np.ones(len(group))]
        if mcap_col in group.columns and group[mcap_col].notna().any():
            X_parts.append(group[mcap_col].fillna(group[mcap_col].median()).to_numpy())
        if industry_col in group.columns and group[industry_col].notna().any():
            dummies = pd.get_dummies(group[industry_col].fillna("UNK"), drop_first=True)
            if not dummies.empty:
                X_parts.append(dummies.to_numpy(dtype=float))
        X = np.column_stack(X_parts)
        try:
            beta, _, _, _ = np.linalg.lstsq(X, y.to_numpy(), rcond=None)
            fitted = X @ beta
            residuals.loc[group.index] = y.to_numpy() - fitted
        except Exception:
            residuals.loc[group.index] = y - y.mean()
    return residuals


def group_quantile_excess(
    df: pd.DataFrame,
    *,
    factor_col: str = "factor",
    return_col: str = "ret_1d",
    n_groups: int = 5,
) -> Dict[str, float]:
    """Mean return of top quantile minus bottom quantile (pooled)."""
    work = df.dropna(subset=[factor_col, return_col]).copy()
    if work.empty or work[factor_col].nunique() < 2:
        return {f"Q{i+1}": 0.0 for i in range(n_groups)} | {"long_short": 0.0}
    try:
        work["q"] = pd.qcut(work[factor_col], q=n_groups, labels=False, duplicates="drop")
    except ValueError:
        work["q"] = pd.cut(work[factor_col], bins=n_groups, labels=False, duplicates="drop")
    means = work.groupby("q")[return_col].mean()
    out = {f"Q{int(i)+1}": float(means.get(i, 0.0)) for i in range(n_groups)}
    qmax, qmin = means.index.max(), means.index.min()
    out["long_short"] = float(means.get(qmax, 0.0) - means.get(qmin, 0.0))
    return out


def run_factor_backtest(
    factor_df: pd.DataFrame,
    price_df: pd.DataFrame,
    *,
    benchmark_df: Optional[pd.DataFrame] = None,
    horizons: Sequence[int] = (1, 3, 5),
    factor_col: str = "factor",
    date_col: str = "trade_date",
    neutralize: bool = True,
    n_groups: int = 5,
) -> FactorBacktestReport:
    """Core validation loop for sentiment factor.

    ``factor_df`` columns: trade_date, symbol, factor [, industry, log_mcap]
    ``price_df`` columns: date, symbol, close
    """
    prices = attach_forward_returns(price_df, horizons=horizons)
    fac = factor_df.copy()
    fac[date_col] = pd.to_datetime(fac[date_col], errors="coerce")
    if neutralize:
        fac["factor_raw"] = fac[factor_col]
        fac[factor_col] = neutralize_factor(fac, factor_col=factor_col, date_col=date_col)

    merged = fac.merge(
        prices,
        left_on=[date_col, "symbol"],
        right_on=["date", "symbol"],
        how="inner",
    )
    report = FactorBacktestReport(
        n_days=int(merged[date_col].nunique()) if not merged.empty else 0,
        n_obs=int(len(merged)),
    )
    if merged.empty:
        return report

    for h in horizons:
        ret_col = f"ret_{h}d"
        sub = merged.dropna(subset=[factor_col, ret_col])
        mean_ic, icir, period_ics = rolling_date_ic(
            sub.rename(columns={ret_col: "next_return"}),
            date_col=date_col,
            factor_col=factor_col,
            return_col="next_return",
        )
        # Also compute pooled IC for small universes
        pooled = compute_factor_ic(sub[factor_col].tolist(), sub[ret_col].tolist())
        groups = group_quantile_excess(
            sub, factor_col=factor_col, return_col=ret_col, n_groups=n_groups
        )
        report.horizons[int(h)] = {
            "ic_mean": mean_ic if period_ics else pooled,
            "ic_pooled": pooled,
            "icir": icir,
            "long_short_excess": groups.get("long_short", 0.0),
            "n_obs": float(len(sub)),
        }
        if h == 1:
            report.group_excess = groups

    # Performance vs HS300: long top-quintile equal-weight daily
    h1 = merged.dropna(subset=[factor_col, "ret_1d"]).copy()
    if not h1.empty:
        def _top_ret(g: pd.DataFrame) -> float:
            if len(g) < 2:
                return float(g["ret_1d"].mean())
            thr = g[factor_col].quantile(0.8)
            top = g[g[factor_col] >= thr]
            return float(top["ret_1d"].mean()) if not top.empty else float(g["ret_1d"].mean())

        daily = h1.groupby(date_col).apply(_top_ret, include_groups=False)
        strat_rets = daily.dropna().tolist()
        if benchmark_df is not None and not benchmark_df.empty:
            b = benchmark_df.copy()
            b["date"] = pd.to_datetime(b["date"], errors="coerce")
            b = b.sort_values("date")
            b["bench_ret"] = b["close"].pct_change()
            bench_map = b.set_index("date")["bench_ret"].to_dict()
            bench_rets = [float(bench_map.get(pd.Timestamp(d), 0.0) or 0.0) for d in daily.index]
        else:
            bench_rets = [0.0] * len(strat_rets)

        excess = compute_excess_return(strat_rets, bench_rets)
        # Equity metrics
        equity = [100.0]
        for r in strat_rets:
            equity.append(equity[-1] * (1.0 + float(r)))
        perf = compute_performance_metrics(equity)
        report.vs_benchmark = {
            **excess,
            "sharpe": float(perf.get("sharpe", 0.0)),
            "max_drawdown": float(perf.get("max_drawdown", 0.0)),
            "annual_return": float(perf.get("annual_return", 0.0)),
        }
    return report


def save_factor_backtest_report(
    report: FactorBacktestReport, report_dir: str, tag: str = ""
) -> str:
    path = Path(report_dir)
    path.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"factor_backtest_{tag + '_' if tag else ''}{ts}.md"
    target = path / name
    lines = [
        f"# Factor Backtest Report - {ts}",
        "",
        f"- Observations: {report.n_obs}",
        f"- Trading days: {report.n_days}",
        "",
        "## Lead-lag (IC / ICIR / long-short)",
    ]
    for h, stats in sorted(report.horizons.items()):
        lines.append(
            f"- T+{h}: IC={stats['ic_mean']:.4f}, IC_pooled={stats['ic_pooled']:.4f}, "
            f"ICIR={stats['icir']:.4f}, L/S={stats['long_short_excess']:.4%}, n={int(stats['n_obs'])}"
        )
    lines.append("")
    lines.append("## Group excess (T+1)")
    for k, v in report.group_excess.items():
        lines.append(f"- {k}: {v:.4%}")
    lines.append("")
    lines.append("## Vs HS300 benchmark (top-quintile)")
    for k, v in report.vs_benchmark.items():
        if "drawdown" in k or "return" in k or "ann" in k:
            lines.append(f"- {k}: {v:.2%}" if abs(v) < 10 else f"- {k}: {v:.4f}")
        else:
            lines.append(f"- {k}: {v:.4f}")
    target.write_text("\n".join(lines), encoding="utf-8")
    return str(target)
