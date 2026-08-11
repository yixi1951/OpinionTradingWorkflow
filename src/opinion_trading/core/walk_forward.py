"""Walk-forward / hold-out evaluation to reduce in-sample overfitting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

from opinion_trading.core.evaluation import EvalSummary, evaluate_signals, load_signals
from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class WalkForwardFold:
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    train_summary: EvalSummary
    test_summary: EvalSummary
    degradation_accuracy: float
    degradation_sharpe: float


@dataclass
class WalkForwardReport:
    folds: List[WalkForwardFold]
    avg_test_accuracy: float
    avg_test_sharpe: float
    avg_degradation_accuracy: float
    recommendation: str


def run_walk_forward(
    signal_path: str,
    price_df: pd.DataFrame,
    end_date: Optional[date] = None,
    n_folds: int = 3,
    train_days: int = 60,
    test_days: int = 20,
    min_signals_per_fold: int = 3,
) -> WalkForwardReport:
    """Rolling train/test splits on calendar days (uses signal_history.jsonl)."""
    signals = load_signals(signal_path)
    if signals.empty or "trade_date" not in signals.columns:
        return _empty_report("无历史信号，请先运行 daily 模式积累 signal_history.jsonl")

    signals = signals.dropna(subset=["trade_date"])
    max_dt = signals["trade_date"].max()
    if end_date is None:
        end_date = max_dt.date() if hasattr(max_dt, "date") else date.today()

    folds: List[WalkForwardFold] = []
    cursor_end = end_date

    for _ in range(n_folds):
        test_end = cursor_end
        test_start = test_end - timedelta(days=test_days - 1)
        train_end = test_start - timedelta(days=1)
        train_start = train_end - timedelta(days=train_days - 1)

        train_merged, train_sum = evaluate_signals(
            signals,
            price_df,
            start_date=train_start.isoformat(),
            end_date=train_end.isoformat(),
        )
        test_merged, test_sum = evaluate_signals(
            signals,
            price_df,
            start_date=test_start.isoformat(),
            end_date=test_end.isoformat(),
        )

        if test_sum.total_signals < min_signals_per_fold and train_sum.total_signals < min_signals_per_fold:
            cursor_end = train_start - timedelta(days=1)
            continue

        deg_acc = train_sum.accuracy - test_sum.accuracy
        deg_sh = train_sum.sharpe_like - test_sum.sharpe_like
        folds.append(
            WalkForwardFold(
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_summary=train_sum,
                test_summary=test_sum,
                degradation_accuracy=deg_acc,
                degradation_sharpe=deg_sh,
            )
        )
        cursor_end = train_start - timedelta(days=1)

    if not folds:
        return _empty_report("样本不足，无法划分 walk-forward 折")

    avg_test_acc = sum(f.test_summary.accuracy for f in folds) / len(folds)
    avg_test_sh = sum(f.test_summary.sharpe_like for f in folds) / len(folds)
    avg_deg = sum(f.degradation_accuracy for f in folds) / len(folds)
    rec = _recommendation(avg_test_acc, avg_test_sh, avg_deg)
    return WalkForwardReport(
        folds=folds,
        avg_test_accuracy=avg_test_acc,
        avg_test_sharpe=avg_test_sh,
        avg_degradation_accuracy=avg_deg,
        recommendation=rec,
    )


def save_walk_forward_report(report_dir: str, report: WalkForwardReport) -> Path:
    out = Path(report_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "walk_forward_report.md"
    lines = [
        "# Walk-Forward 样本外评估",
        "",
        f"- 平均测试集准确率: **{report.avg_test_accuracy:.2%}**",
        f"- 平均测试 Sharpe-like: **{report.avg_test_sharpe:.4f}**",
        f"- 平均训练→测试准确率落差: **{report.avg_degradation_accuracy:+.2%}**",
        "",
        "## 结论",
        report.recommendation,
        "",
        "## 各折明细",
        "",
        "| 训练期 | 测试期 | 训练准确率 | 测试准确率 | 训练 Sharpe | 测试 Sharpe |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for f in report.folds:
        lines.append(
            f"| {f.train_start} ~ {f.train_end} | {f.test_start} ~ {f.test_end} | "
            f"{f.train_summary.accuracy:.2%} | {f.test_summary.accuracy:.2%} | "
            f"{f.train_summary.sharpe_like:.4f} | {f.test_summary.sharpe_like:.4f} |"
        )
    target.write_text("\n".join(lines), encoding="utf-8")
    from opinion_trading.core.walk_forward_cache import save_walk_forward_json

    save_walk_forward_json(report_dir, report)
    return target


def _recommendation(avg_test_acc: float, avg_test_sh: float, avg_deg: float) -> str:
    if avg_test_acc < 0.45 and avg_test_sh < 0:
        return (
            "样本外表现偏弱，存在过拟合或数据噪音风险；"
            "建议扩大股票池与历史窗口、启用多因子共识，并避免在样本内调参后直接实盘。"
        )
    if avg_deg > 0.15:
        return (
            "训练集明显优于测试集（准确率落差 >15%），提示过拟合；"
            "请优先使用 walk-forward 指标而非全样本回测 Sharpe。"
        )
    return (
        "样本外指标可接受，但仍仅为研究原型；"
        "需结合纸面交易与数据质量报告，勿直接对接实盘下单。"
    )


def _empty_report(msg: str) -> WalkForwardReport:
    return WalkForwardReport(
        folds=[],
        avg_test_accuracy=0.0,
        avg_test_sharpe=0.0,
        avg_degradation_accuracy=0.0,
        recommendation=msg,
    )
