"""Append-only event log: signals vs fills (audit trail for paper / future live)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

EVENT_TYPES = (
    "signal_emitted",
    "signal_blocked",
    "execution_intent",
    "paper_fill",
    "risk_reject",
)


def append_event(
    memory_dir: str,
    event_type: str,
    payload: Dict[str, Any],
    *,
    trade_date: Optional[str] = None,
) -> Path:
    root = Path(memory_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "event_log.jsonl"
    row = {
        "ts": datetime.now().isoformat(),
        "event_type": event_type,
        "trade_date": trade_date,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return path


def load_recent_events(memory_dir: str, limit: int = 50) -> List[Dict[str, Any]]:
    path = Path(memory_dir) / "event_log.jsonl"
    if not path.exists():
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