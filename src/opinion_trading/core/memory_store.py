from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


class JsonLineMemoryStore:
    def __init__(self, memory_dir: str) -> None:
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def append_many(self, file_name: str, records: Iterable[Dict[str, Any]]) -> None:
        target = self.memory_dir / file_name
        with target.open("a", encoding="utf-8") as f:
            for row in records:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def read_all(self, file_name: str) -> List[Dict[str, Any]]:
        target = self.memory_dir / file_name
        if not target.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with target.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def save_state(self, state: Dict[str, Any], file_name: str = "state.json") -> None:
        target = self.memory_dir / file_name
        with target.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self, file_name: str = "state.json") -> Dict[str, Any]:
        target = self.memory_dir / file_name
        if not target.exists():
            return {}
        with target.open("r", encoding="utf-8") as f:
            return json.load(f)
