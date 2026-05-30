from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from opinion_trading.core.evaluation import evaluate_signals, load_signals
from opinion_trading.core.price_fetcher import fetch_prices


@dataclass
class MonthlyTrainingSummary:
    months_trained: int
    start_month: str
    end_month: str
    total_signals: int
    latest_month_accuracy: float
    rolling_success_rate: float
    rolling_avg_return: float
    rolling_win_rate: float
    forecast_success_rate: float
    forecast_direction: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def build_monthly_training_frame(
    signal_df: pd.DataFrame,
    price_df: pd.DataFrame,
    months: int = 6,
) -> Tuple[pd.DataFrame, MonthlyTrainingSummary]:
    if signal_df.empty:
        summary = MonthlyTrainingSummary(
            months_trained=0,
            start_month="",
            end_month="",
            total_signals=0,
            latest_month_accuracy=0.0,
            rolling_success_rate=0.0,
            rolling_avg_return=0.0,
            rolling_win_rate=0.0,
            forecast_success_rate=0.0,
            forecast_direction="NEUTRAL",
        )
        return pd.DataFrame(columns=[
            "month",
            "signals",
            "correct_signals",
            "accuracy",
            "avg_return",
            "win_rate",
            "avg_confidence",
            "bullish_signals",
            "bearish_signals",
        ]), summary

    merged, _ = evaluate_signals(signal_df, price_df)
    if merged.empty:
        summary = MonthlyTrainingSummary(
            months_trained=0,
            start_month="",
            end_month="",
            total_signals=0,
            latest_month_accuracy=0.0,
            rolling_success_rate=0.0,
            rolling_avg_return=0.0,
            rolling_win_rate=0.0,
            forecast_success_rate=0.0,
            forecast_direction="NEUTRAL",
        )
        return pd.DataFrame(columns=[
            "month",
            "signals",
            "correct_signals",
            "accuracy",
            "avg_return",
            "win_rate",
            "avg_confidence",
            "bullish_signals",
            "bearish_signals",
        ]), summary

    valid = merged.dropna(subset=["next_return", "correct"]).copy()
    if valid.empty:
        summary = MonthlyTrainingSummary(
            months_trained=0,
            start_month="",
            end_month="",
            total_signals=0,
            latest_month_accuracy=0.0,
            rolling_success_rate=0.0,
            rolling_avg_return=0.0,
            rolling_win_rate=0.0,
            forecast_success_rate=0.0,
            forecast_direction="NEUTRAL",
        )
        return pd.DataFrame(columns=[
            "month",
            "signals",
            "correct_signals",
            "accuracy",
            "avg_return",
            "win_rate",
            "avg_confidence",
            "bullish_signals",
            "bearish_signals",
        ]), summary

    valid["month"] = valid["trade_date"].dt.to_period("M").astype(str)
    valid["is_bullish"] = valid["action"].astype(str).str.upper().eq("BUY")

    monthly = (
        valid.groupby("month", as_index=False)
        .agg(
            signals=("symbol", "size"),
            correct_signals=("correct", "sum"),
            accuracy=("correct", "mean"),
            avg_return=("next_return", "mean"),
            win_rate=("next_return", lambda s: float((s > 0).mean())),
            avg_confidence=("confidence", "mean"),
            bullish_signals=("is_bullish", "sum"),
        )
    )
    monthly["bearish_signals"] = monthly["signals"] - monthly["bullish_signals"]

    monthly = monthly.sort_values("month").reset_index(drop=True)
    if months > 0:
        monthly = monthly.tail(months).reset_index(drop=True)

    if monthly.empty:
        summary = MonthlyTrainingSummary(
            months_trained=0,
            start_month="",
            end_month="",
            total_signals=0,
            latest_month_accuracy=0.0,
            rolling_success_rate=0.0,
            rolling_avg_return=0.0,
            rolling_win_rate=0.0,
            forecast_success_rate=0.0,
            forecast_direction="NEUTRAL",
        )
        return monthly, summary

    tail = monthly.tail(min(3, len(monthly))).copy()
    weights = pd.Series(range(1, len(tail) + 1), index=tail.index, dtype=float)
    weight_total = float(weights.sum()) if not weights.empty else 1.0

    forecast_success_rate = float((tail["accuracy"] * weights).sum() / weight_total) if weight_total > 0 else 0.0
    rolling_avg_return = float((tail["avg_return"] * weights).sum() / weight_total) if weight_total > 0 else 0.0
    rolling_win_rate = float((tail["win_rate"] * weights).sum() / weight_total) if weight_total > 0 else 0.0

    if rolling_avg_return > 0.002:
        forecast_direction = "BULLISH"
    elif rolling_avg_return < -0.002:
        forecast_direction = "BEARISH"
    else:
        forecast_direction = "NEUTRAL"

    summary = MonthlyTrainingSummary(
        months_trained=int(len(monthly)),
        start_month=str(monthly["month"].iloc[0]),
        end_month=str(monthly["month"].iloc[-1]),
        total_signals=int(monthly["signals"].sum()),
        latest_month_accuracy=float(monthly["accuracy"].iloc[-1]),
        rolling_success_rate=float(monthly["accuracy"].mean()),
        rolling_avg_return=rolling_avg_return,
        rolling_win_rate=rolling_win_rate,
        forecast_success_rate=forecast_success_rate,
        forecast_direction=forecast_direction,
    )
    return monthly, summary


def load_training_history(memory_dir: str) -> pd.DataFrame:
    frames = []

    signal_path = Path(memory_dir) / "signal_history.jsonl"
    if signal_path.exists():
        signal_df = load_signals(str(signal_path))
        if not signal_df.empty:
            frames.append(signal_df)

    pick_path = Path(memory_dir) / "realtime_pick_history.jsonl"
    if pick_path.exists():
        rows = []
        for line in pick_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))
        if rows:
            pick_df = pd.DataFrame(rows)
            if "trade_date" in pick_df.columns:
                pick_df["trade_date"] = pd.to_datetime(pick_df["trade_date"], errors="coerce")
            if "action" not in pick_df.columns:
                score_col = "score" if "score" in pick_df.columns else "avg_score" if "avg_score" in pick_df.columns else None
                if score_col is not None:
                    pick_df["action"] = pick_df[score_col].apply(lambda v: "BUY" if float(v) >= 0 else "SELL")
            if "confidence" not in pick_df.columns:
                score_col = "score" if "score" in pick_df.columns else "avg_score" if "avg_score" in pick_df.columns else None
                if score_col is not None:
                    pick_df["confidence"] = pick_df[score_col].abs().clip(0.0, 1.0)
                else:
                    pick_df["confidence"] = 0.0
            if "reason" not in pick_df.columns:
                pick_df["reason"] = "realtime pick history"
            if "platforms" not in pick_df.columns:
                pick_df["platforms"] = [[] for _ in range(len(pick_df))]
            frames.append(pick_df[["trade_date", "symbol", "action", "confidence", "reason", "platforms"]].copy())

    report_df = load_training_history_from_reports(str(Path(memory_dir).parent / "reports"))
    if not report_df.empty:
        frames.append(report_df)

    if not frames:
        return pd.DataFrame(columns=["trade_date", "symbol", "action", "confidence", "reason", "platforms"])

    combined = pd.concat(frames, ignore_index=True)
    combined["trade_date"] = pd.to_datetime(combined["trade_date"], errors="coerce")
    combined = combined.dropna(subset=["trade_date", "symbol"])
    combined = combined.drop_duplicates(subset=["trade_date", "symbol", "action"], keep="last")
    return combined[["trade_date", "symbol", "action", "confidence", "reason", "platforms"]].copy()


def load_training_history_from_reports(report_dir: str) -> pd.DataFrame:
    report_path = Path(report_dir)
    rows = []
    pattern = re.compile(r"realtime_picks_(\d{8})_\d{6}\.csv$")

    for csv_file in sorted(report_path.glob("realtime_picks_*.csv")):
        match = pattern.search(csv_file.name)
        if not match:
            continue
        trade_date = datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()
        try:
            pick_df = pd.read_csv(csv_file)
        except Exception:
            continue
        if pick_df.empty:
            continue
        for _, row in pick_df.iterrows():
            score_value = float(row.get("avg_score", 0.0)) if not pd.isna(row.get("avg_score", 0.0)) else 0.0
            rows.append(
                {
                    "trade_date": trade_date,
                    "symbol": str(row.get("symbol", "")),
                    "action": "BUY" if score_value >= 0 else "SELL",
                    "confidence": abs(score_value),
                    "reason": "realtime pick report replay",
                    "platforms": [],
                }
            )

    if not rows:
        return pd.DataFrame(columns=["trade_date", "symbol", "action", "confidence", "reason", "platforms"])

    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df.dropna(subset=["trade_date", "symbol"])
    return df[["trade_date", "symbol", "action", "confidence", "reason", "platforms"]].copy()


def save_monthly_training_report(
    report_dir: str,
    monthly_df: pd.DataFrame,
    summary: MonthlyTrainingSummary,
) -> Dict[str, str]:
    report_path = Path(report_dir)
    report_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = report_path / f"monthly_training_{ts}.csv"
    md_path = report_path / f"monthly_training_{ts}.md"
    json_path = report_path / f"monthly_training_{ts}.json"

    monthly_df.to_csv(csv_path, index=False)

    payload = {
        "summary": summary.to_dict(),
        "monthly_rows": monthly_df.to_dict(orient="records"),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Monthly Training Report - {ts}",
        "",
        f"- Months trained: {summary.months_trained}",
        f"- Range: {summary.start_month or 'N/A'} -> {summary.end_month or 'N/A'}",
        f"- Total signals: {summary.total_signals}",
        f"- Latest month accuracy: {summary.latest_month_accuracy:.2%}",
        f"- Rolling success rate: {summary.rolling_success_rate:.2%}",
        f"- Rolling avg return: {summary.rolling_avg_return:.4%}",
        f"- Rolling win rate: {summary.rolling_win_rate:.2%}",
        f"- Forecast success rate: {summary.forecast_success_rate:.2%}",
        f"- Forecast direction: {summary.forecast_direction}",
        "",
        "## Monthly rows",
    ]

    if monthly_df.empty:
        lines.append("- No monthly rows available.")
    else:
        for _, row in monthly_df.iterrows():
            lines.append(
                f"- {row['month']} | signals={int(row['signals'])} | correct={int(row['correct_signals'])} | "
                f"accuracy={float(row['accuracy']):.2%} | avg_return={float(row['avg_return']):.4%} | "
                f"win_rate={float(row['win_rate']):.2%}"
            )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"csv": str(csv_path), "md": str(md_path), "json": str(json_path)}


def load_latest_monthly_training(report_dir: str) -> Tuple[pd.DataFrame, Dict[str, object]]:
    report_path = Path(report_dir)
    csv_files = sorted(report_path.glob("monthly_training_*.csv"))
    json_files = sorted(report_path.glob("monthly_training_*.json"))

    monthly_df = pd.DataFrame()
    summary: Dict[str, object] = {}

    if csv_files:
        monthly_df = pd.read_csv(csv_files[-1])
    if json_files:
        try:
            summary = json.loads(json_files[-1].read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary = {}

    return monthly_df, summary


def fetch_prices_with_timeout(
    symbols: list[str],
    start_date: str,
    end_date: str,
    timeout_seconds: int = 20,
) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fetch_prices, symbols, start_date, end_date)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()