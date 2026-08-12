"""Persist / load last successful dashboard snapshot metadata."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_NAME = "last_run.json"


def last_run_path(report_dir: str | Path, file_name: str = DEFAULT_NAME) -> Path:
    return Path(report_dir) / file_name


def save_last_run(
    report_dir: str | Path,
    *,
    mode: str,
    picks_path: str | None = None,
    raw_rows: int | None = None,
    symbols: int | None = None,
    trade_date: str | None = None,
    note: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write a small JSON so the UI can open in snapshot mode without regenerating."""
    path = last_run_path(report_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "picks_path": picks_path,
        "raw_rows": raw_rows,
        "symbols": symbols,
        "trade_date": trade_date,
        "note": note,
        "view_only_default": True,
    }
    if extra:
        payload.update(extra)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def load_last_run(report_dir: str | Path) -> Dict[str, Any]:
    path = last_run_path(report_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def format_last_run_caption(meta: Dict[str, Any], *, lang: str = "zh") -> str:
    if not meta:
        return (
            "当前为只读查看：尚未记录上次生成时间（打开不会自动采集）。"
            if lang == "zh"
            else "View-only: no last-run stamp yet (open does not auto-collect)."
        )
    when = meta.get("updated_at") or meta.get("trade_date") or "—"
    mode = meta.get("mode") or "—"
    picks = meta.get("picks_path") or ""
    picks_name = Path(str(picks)).name if picks else "—"
    if lang == "zh":
        return (
            f"只读上次结果 · 生成于 {when} · 模式 {mode} · 选股文件 {picks_name}"
            f"（打开页面不会重新采集；需要时再点「重新生成」）"
        )
    return (
        f"Viewing last run · {when} · mode {mode} · picks {picks_name}"
        f" (open does not re-collect; click Regenerate when needed)"
    )
