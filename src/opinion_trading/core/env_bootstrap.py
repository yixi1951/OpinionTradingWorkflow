"""Load project-root `.env` into os.environ (no extra dependency)."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_if_present(start: Path | None = None) -> Path | None:
    """Set unset keys from `.env`; returns path if loaded."""
    root = start or Path.cwd()
    for _ in range(6):
        candidate = root / ".env"
        if candidate.is_file():
            _apply_env_file(candidate)
            return candidate
        if root.parent == root:
            break
        root = root.parent
    return None


def _apply_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val