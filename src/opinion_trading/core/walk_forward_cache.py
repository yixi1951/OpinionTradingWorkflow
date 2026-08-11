"""Persist walk-forward report for UI fold table (JSON + CSV export)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, List

from opinion_trading.core.walk_forward import WalkForwardReport


def walk_forward_report_to_dict(report: WalkForwardReport) -> Dict[str, Any]:
    folds: List[Dict[str, Any]] = []
    for f in report.folds:
        folds.append(
            {
                "train_start": f.train_start.isoformat(),
                "train_end": f.train_end.isoformat(),
                "test_start": f.test_start.isoformat(),
                "test_end": f.test_end.isoformat(),
                "train_accuracy": f.train_summary.accuracy,
                "test_accuracy": f.test_summary.accuracy,
                "train_sharpe": f.train_summary.sharpe_like,
                "test_sharpe": f.test_summary.sharpe_like,
                "degradation_accuracy": f.degradation_accuracy,
                "degradation_sharpe": f.degradation_sharpe,
                "train_signals": f.train_summary.total_signals,
                "test_signals": f.test_summary.total_signals,
            }
        )
    return {
        "avg_test_accuracy": report.avg_test_accuracy,
        "avg_test_sharpe": report.avg_test_sharpe,
        "avg_degradation_accuracy": report.avg_degradation_accuracy,
        "recommendation": report.recommendation,
        "folds": folds,
    }


def save_walk_forward_json(report_dir: str, report: WalkForwardReport) -> Path:
    out = Path(report_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "walk_forward_report.json"
    target.write_text(
        json.dumps(walk_forward_report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def load_walk_forward_json(report_dir: str) -> Dict[str, Any] | None:
    path = Path(report_dir) / "walk_forward_report.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def export_walk_forward_folds_csv(report_dir: str) -> bytes:
    """UTF-8 CSV bytes for Streamlit download (from JSON cache)."""
    data = load_walk_forward_json(report_dir)
    if not data or not data.get("folds"):
        return b"fold,train_start,train_end,test_start,test_end,train_accuracy,test_accuracy,degradation_accuracy\n"

    buf = io.StringIO()
    fields = [
        "fold",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "train_accuracy",
        "test_accuracy",
        "train_sharpe",
        "test_sharpe",
        "degradation_accuracy",
        "train_signals",
        "test_signals",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for i, row in enumerate(data["folds"], start=1):
        writer.writerow({"fold": i, **row})
    return buf.getvalue().encode("utf-8-sig")
