"""Structured audit trail: signal → decision → order → ack (JSONL)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def new_trace_id(prefix: str = "tr") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


class AuditLogger:
    """Append-only JSONL audit log with trace_id / order_id."""

    def __init__(self, path: str = "data/memory/audit_trail.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        event: str,
        *,
        trace_id: str | None = None,
        order_id: str | None = None,
        **fields: Any,
    ) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            "trace_id": trace_id or new_trace_id(),
            "order_id": order_id or "",
            "env": os.environ.get("APP_ENV", "dev"),
        }
        row.update({k: v for k, v in fields.items() if v is not None})
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return row
