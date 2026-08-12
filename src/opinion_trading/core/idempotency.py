"""File-backed idempotency store for signals / order intents."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from opinion_trading.core.http_retry import make_idempotency_key


class IdempotencyStore:
    """Persist seen request/event ids so retries do not double-submit."""

    def __init__(self, root: str = "data/memory/idempotency") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, namespace: str) -> Path:
        safe = "".join(c for c in namespace if c.isalnum() or c in "-_")[:64] or "default"
        return self.root / f"{safe}.jsonl"

    def seen(self, namespace: str, key: str) -> bool:
        key = str(key or "").strip()
        if not key:
            return False
        path = self._path(namespace)
        if not path.exists():
            return False
        with self._lock:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("key")) == key:
                    return True
        return False

    def remember(
        self,
        namespace: str,
        key: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Return True if newly recorded, False if duplicate."""
        key = str(key or "").strip()
        if not key:
            key = make_idempotency_key(prefix=namespace)
        if self.seen(namespace, key):
            return False
        path = self._path(namespace)
        row = {
            "key": key,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "payload": payload or {},
        }
        with self._lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True

    def get(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        key = str(key or "").strip()
        if not key:
            return None
        path = self._path(namespace)
        if not path.exists():
            return None
        with self._lock:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("key")) == key:
                    return row
        return None
