from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class EvalSummary:
    total_signals: int
    accuracy: float
    avg_return: float
    win_rate: float
    sharpe_like: float


def load_signals(signal_path: str) -> pd.DataFrame:
    path = Path(signal_path)
    if not path.exists():
        return pd.DataFrame(columns=["trade_date", "symbol", "action", "confidence", "reason", "platforms"])
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame(columns=["trade_date", "symbol", "action", "confidence", "reason", "platforms"])
    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    return df


def load_prices(price_csv: str) -> pd.DataFrame:
    df = pd.read_csv(price_csv)
    return normalize_price_frame(df)


def normalize_price_frame(price_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.copy()
    if "date" not in df.columns or "symbol" not in df.columns or "close" not in df.columns:
        raise ValueError("price CSV must contain columns: date, symbol, close")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "close"])
    return df


def compute_next_returns(price_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.sort_values(["symbol", "date"]).copy()
    df["next_close"] = df.groupby("symbol")["close"].shift(-1)
    df["next_return"] = (df["next_close"] - df["close"]) / df["close"]
    return df


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
            s_sub = signal_df[signal_df["symbol"] == sym].sort_values("trade_date").copy()
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
    valid = merged.dropna(subset=["next_return", "correct"])

    total = int(valid.shape[0])
    if total == 0:
        summary = EvalSummary(0, 0.0, 0.0, 0.0, 0.0)
        return merged, summary

    accuracy = float(valid["correct"].mean())
    avg_return = float(valid["next_return"].mean())
    win_rate = float((valid["next_return"] > 0).mean())
    std_return = float(valid["next_return"].std(ddof=0)) if total > 1 else 0.0
    sharpe_like = avg_return / (std_return + 1e-6)

    summary = EvalSummary(total, accuracy, avg_return, win_rate, sharpe_like)
    return merged, summary


def save_evaluation(report_dir: str, merged: pd.DataFrame, summary: EvalSummary) -> Dict[str, str]:
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
        f"- Total signals: {summary.total_signals}",
        f"- Accuracy: {summary.accuracy:.2%}",
        f"- Avg next-day return: {summary.avg_return:.4%}",
        f"- Win rate: {summary.win_rate:.2%}",
        f"- Sharpe-like: {summary.sharpe_like:.4f}",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {"csv": str(csv_path), "md": str(md_path)}
