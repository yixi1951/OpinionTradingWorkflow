from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from opinion_trading.core.factor_metrics import (
    compute_excess_return,
    rolling_date_ic,
)


@dataclass
class EvalSummary:
    total_signals: int
    accuracy: float
    avg_return: float
    win_rate: float
    sharpe_like: float
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    payoff_ratio: float = 0.0
    calmar_like: float = 0.0
    # Factor / selection validation
    factor_ic: float = 0.0
    factor_icir: float = 0.0
    annualized_return: float = 0.0
    excess_return_ann: float = 0.0
    benchmark_ann: float = 0.0
    signal_coverage: float = 0.0
    signal_validity_rate: float = 0.0


def load_signals(signal_path: str) -> pd.DataFrame:
    path = Path(signal_path)
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "trade_date",
                "symbol",
                "action",
                "confidence",
                "reason",
                "platforms",
            ]
        )
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "symbol",
                "action",
                "confidence",
                "reason",
                "platforms",
            ]
        )
    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    return df


def load_prices(price_csv: str) -> pd.DataFrame:
    df = pd.read_csv(price_csv)
    return normalize_price_frame(df)


def normalize_price_frame(price_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.copy()
    if (
        "date" not in df.columns
        or "symbol" not in df.columns
        or "close" not in df.columns
    ):
        raise ValueError("price CSV must contain columns: date, symbol, close")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "close"])
    return df


def compute_next_returns(price_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.sort_values(["symbol", "date"]).copy()
    df["next_close"] = df.groupby("symbol")["close"].shift(-1)
    df["next_return"] = (df["next_close"] - df["close"]) / df["close"]
    return df


def _signal_factor(row) -> float:
    """Map trade action + confidence to a signed factor score for IC."""
    conf = float(row.get("confidence", 0.0) or 0.0)
    act = str(row.get("action", "")).upper()
    if act == "BUY":
        return conf
    if act == "SELL":
        return -conf
    score = row.get("consensus_score", row.get("score"))
    try:
        return float(score) if score is not None and score != "" else 0.0
    except (TypeError, ValueError):
        return 0.0


def evaluate_signals(
    signal_df: pd.DataFrame,
    price_df: pd.DataFrame,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[pd.DataFrame, EvalSummary]:
    if signal_df.empty:
        summary = EvalSummary(0, 0.0, 0.0, 0.0, 0.0)
        return pd.DataFrame(), summary

    if start_date:
        signal_df = signal_df[signal_df["trade_date"] >= pd.to_datetime(start_date)]
    if end_date:
        signal_df = signal_df[signal_df["trade_date"] <= pd.to_datetime(end_date)]

    # normalize and compute next-day returns for available prices
    prices = normalize_price_frame(price_df)
    prices = compute_next_returns(prices)
    prices_full = prices.copy()
    prices = prices[["date", "symbol", "close", "next_return"]]

    # If there is no direct date overlap between signals and prices, try an asof-style
    # fallback: for each symbol, match the signal to the most recent available price
    # on or before the signal's trade_date. This provides a sensible fallback when
    # price CSV is a historical snapshot that doesn't include the exact signal dates.
    if not signal_df["trade_date"].isin(prices["date"]).any():
        import warnings

        warnings.warn(
            "No direct overlap between signal trade_date and price dates; using nearest prior price per symbol as fallback",
            UserWarning,
        )

        frames = []
        for sym in signal_df["symbol"].dropna().unique():
            s_sub = (
                signal_df[signal_df["symbol"] == sym].sort_values("trade_date").copy()
            )
            p_sub = prices[prices["symbol"] == sym].sort_values("date").copy()
            # only keep price rows that have a computable next_return
            p_sub = p_sub.dropna(subset=["next_return"])
            if p_sub.empty or s_sub.empty:
                continue
            merged_sub = pd.merge_asof(
                s_sub,
                p_sub,
                left_on="trade_date",
                right_on="date",
                direction="backward",
                allow_exact_matches=True,
            )
            frames.append(merged_sub)
        if frames:
            merged = pd.concat(frames, ignore_index=True)
        else:
            # fallback to regular merge if no per-symbol prices available
            merged = signal_df.merge(
                prices,
                left_on=["trade_date", "symbol"],
                right_on=["date", "symbol"],
                how="left",
            )
    else:
        merged = signal_df.merge(
            prices,
            left_on=["trade_date", "symbol"],
            right_on=["date", "symbol"],
            how="left",
        )

    # Ensure a canonical `symbol` column exists after merges (merge_asof may produce symbol_x/symbol_y)
    if "symbol" not in merged.columns:
        if "symbol_x" in merged.columns:
            merged["symbol"] = merged["symbol_x"]
        elif "symbol_y" in merged.columns:
            merged["symbol"] = merged["symbol_y"]
    for c in ("symbol_x", "symbol_y"):
        if c in merged.columns:
            merged = merged.drop(columns=[c])

    def _is_correct(row) -> Optional[bool]:
        if pd.isna(row.get("next_return")):
            return None
        if str(row.get("action")).upper() == "BUY":
            return row.get("next_return", 0.0) > 0
        if str(row.get("action")).upper() == "SELL":
            return row.get("next_return", 0.0) < 0
        return None

    merged["correct"] = merged.apply(_is_correct, axis=1)
    merged["factor"] = merged.apply(_signal_factor, axis=1)
    total_raw = int(merged.shape[0])
    valid = merged.dropna(subset=["next_return", "correct"])

    total = int(valid.shape[0])
    signal_coverage = float(total / total_raw) if total_raw else 0.0
    if total == 0:
        summary = EvalSummary(
            0,
            0.0,
            0.0,
            0.0,
            0.0,
            signal_coverage=signal_coverage,
            signal_validity_rate=0.0,
        )
        return merged, summary

    accuracy = float(valid["correct"].mean())
    avg_return = float(valid["next_return"].mean())
    win_rate = float((valid["next_return"] > 0).mean())
    std_return = float(valid["next_return"].std(ddof=0)) if total > 1 else 0.0
    sharpe_like = avg_return / (std_return + 1e-6)

    def _signed_return(row) -> float:
        act = str(row.get("action", "")).upper()
        r = float(row.get("next_return", 0.0))
        if act == "SELL":
            return -r
        return r

    valid = valid.copy()
    valid["strategy_return"] = valid.apply(_signed_return, axis=1)
    rets = valid["strategy_return"]
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    profit_factor = (
        gross_profit / gross_loss if gross_loss > 1e-12 else (999.0 if gross_profit > 0 else 0.0)
    )
    payoff_ratio = avg_win / (abs(avg_loss) + 1e-12) if avg_loss < 0 else 0.0

    equity = (1.0 + rets).cumprod()
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0, 1e-12)
    max_drawdown = float(dd.min()) if len(dd) else 0.0
    calmar_like = avg_return / (abs(max_drawdown) + 1e-6)

    # Equal-weight universe benchmark on overlapping signal dates
    bench_map = (
        prices_full.dropna(subset=["next_return"])
        .groupby("date")["next_return"]
        .mean()
        .to_dict()
    )
    bench_rets = []
    for _, row in valid.iterrows():
        d = row.get("date", row.get("trade_date"))
        if pd.isna(d):
            bench_rets.append(0.0)
            continue
        bench_rets.append(float(bench_map.get(pd.Timestamp(d), 0.0)))
    excess_stats = compute_excess_return(rets.tolist(), bench_rets)

    factor_ic, factor_icir, _ = rolling_date_ic(
        valid, date_col="trade_date", factor_col="factor", return_col="next_return"
    )

    # Validity: matched price + actionable direction + |factor| above weak noise floor
    valid_mask = valid["factor"].abs() >= 0.05
    signal_validity_rate = float(valid_mask.mean()) if total else 0.0

    summary = EvalSummary(
        total,
        accuracy,
        avg_return,
        win_rate,
        sharpe_like,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        payoff_ratio=payoff_ratio,
        calmar_like=calmar_like,
        factor_ic=factor_ic,
        factor_icir=factor_icir,
        annualized_return=excess_stats["strategy_ann"],
        excess_return_ann=excess_stats["excess_return_ann"],
        benchmark_ann=excess_stats["benchmark_ann"],
        signal_coverage=signal_coverage,
        signal_validity_rate=signal_validity_rate,
    )
    return merged, summary


def save_evaluation(
    report_dir: str, merged: pd.DataFrame, summary: EvalSummary
) -> Dict[str, str]:
    report_path = Path(report_dir)
    report_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = report_path / f"accuracy_eval_{ts}.csv"
    md_path = report_path / f"accuracy_eval_{ts}.md"

    if not merged.empty:
        merged.to_csv(csv_path, index=False)
    else:
        pd.DataFrame().to_csv(csv_path, index=False)

    lines = [
        f"# Accuracy Evaluation - {ts}",
        "",
        "> 标签为 **T+1 收盘收益**（`next_return`），信号日不纳入未来价；无重叠价时用 merge_asof 最近历史价（见 evaluate_signals 警告）。",
        "",
        f"- Total signals: {summary.total_signals}",
        f"- Accuracy: {summary.accuracy:.2%}",
        f"- Avg next-day return: {summary.avg_return:.4%}",
        f"- Win rate: {summary.win_rate:.2%}",
        f"- Sharpe-like: {summary.sharpe_like:.4f}",
        f"- Max drawdown (signal equity curve): {summary.max_drawdown:.2%}",
        f"- Profit factor: {summary.profit_factor:.4f}",
        f"- Payoff ratio (avg win / |avg loss|): {summary.payoff_ratio:.4f}",
        f"- Calmar-like: {summary.calmar_like:.4f}",
        f"- Factor IC (Spearman): {summary.factor_ic:.4f}",
        f"- Factor ICIR: {summary.factor_icir:.4f}",
        f"- Annualized return: {summary.annualized_return:.2%}",
        f"- Benchmark ann (equal-weight): {summary.benchmark_ann:.2%}",
        f"- Excess return ann: {summary.excess_return_ann:.2%}",
        f"- Signal coverage (priced/total): {summary.signal_coverage:.2%}",
        f"- Signal validity rate: {summary.signal_validity_rate:.2%}",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {"csv": str(csv_path), "md": str(md_path)}
