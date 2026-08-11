"""Persist daily quality gate metrics for dashboard charts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from opinion_trading.core.data_quality import QualityGateResult


def append_quality_gate_record(
    memory_dir: str,
    trade_date: str,
    gate: QualityGateResult,
    *,
    raw_row_count: int = 0,
) -> Path:
    root = Path(memory_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "quality_gate_history.jsonl"
    row = {
        "ts": datetime.now().isoformat(),
        "trade_date": trade_date,
        "raw_rows": raw_row_count,
        "overall_pass": gate.overall_pass,
        "fallback_rate": gate.fallback_rate,
        "noise_rate": gate.noise_rate,
        "confidence_multiplier": gate.sentiment_confidence_multiplier,
        "block_new_signals": gate.block_new_signals,
        "messages": gate.messages,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def load_quality_gate_history(
    memory_dir: str,
    *,
    limit: int = 60,
) -> List[Dict[str, Any]]:
    path = Path(memory_dir) / "quality_gate_history.jsonl"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for line in lines[-limit:]:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
