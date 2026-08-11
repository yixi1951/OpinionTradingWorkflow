"""Zip export of reports + memory artifacts for UI download."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, List


def _collect_files(
    base: Path,
    patterns: Iterable[str],
    *,
    max_files: int = 80,
) -> List[Path]:
    found: List[Path] = []
    for pat in patterns:
        for p in sorted(base.glob(pat), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_file() and p.stat().st_size < 50_000_000:
                found.append(p)
            if len(found) >= max_files:
                return found
    return found


def build_dashboard_export_zip(
    report_dir: str,
    memory_dir: str,
    raw_dir: str | None = None,
) -> bytes:
    """Pack recent CSV/MD/JSONL into a single zip (in-memory)."""
    buf = io.BytesIO()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        rd = Path(report_dir)
        if rd.is_dir():
            for f in _collect_files(
                rd,
                [
                    "realtime_picks_*.csv",
                    "realtime_picks_*.md",
                    "realtime_alerts_*.jsonl",
                    "daily_summary_*.csv",
                    "daily_summary_*.md",
                    "walk_forward_report.md",
                    "walk_forward_report.json",
                    "collect_progress_*.jsonl",
                    "accuracy_eval_*.csv",
                    "accuracy_eval_*.md",
                    "quality_*.md",
                    "signals_export_*.csv",
                ],
            ):
                zf.write(f, arcname=f"reports/{f.name}")

        md = Path(memory_dir)
        if md.is_dir():
            for name in (
                "state.json",
                "signal_history.jsonl",
                "trade_history.jsonl",
                "event_log.jsonl",
                "quality_gate_history.jsonl",
            ):
                p = md / name
                if p.is_file():
                    zf.write(p, arcname=f"memory/{name}")

        if raw_dir:
            raw = Path(raw_dir)
            if raw.is_dir():
                for f in _collect_files(raw, ["raw_posts_*.csv"], max_files=5):
                    zf.write(f, arcname=f"raw/{f.name}")

        manifest = (
            f"export_time={ts}\n"
            f"report_dir={report_dir}\n"
            f"memory_dir={memory_dir}\n"
        )
        zf.writestr("README.txt", manifest)
    return buf.getvalue()