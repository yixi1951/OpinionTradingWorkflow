"""Multi-day raw crawl persistence helpers (offline-safe; no network required)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

_RAW_DATE_RE = re.compile(r"^raw_posts_(\d{4}-\d{2}-\d{2})\.csv$")


def list_raw_trade_dates(raw_dir: str | Path) -> List[str]:
    root = Path(raw_dir)
    if not root.is_dir():
        return []
    dates: List[str] = []
    for path in root.iterdir():
        if not path.is_file():
            continue
        m = _RAW_DATE_RE.match(path.name)
        if m:
            dates.append(m.group(1))
    return sorted(set(dates))


def summarize_raw_span(raw_dir: str | Path) -> Dict[str, Any]:
    dates = list_raw_trade_dates(raw_dir)
    if not dates:
        return {
            "raw_dir": str(raw_dir),
            "count": 0,
            "first": None,
            "last": None,
            "gaps": [],
        }
    gaps: List[str] = []
    start = date.fromisoformat(dates[0])
    end = date.fromisoformat(dates[-1])
    have = {date.fromisoformat(d) for d in dates}
    cur = start
    while cur <= end:
        if cur not in have:
            gaps.append(cur.isoformat())
        cur += timedelta(days=1)
    return {
        "raw_dir": str(raw_dir),
        "count": len(dates),
        "first": dates[0],
        "last": dates[-1],
        "calendar_span_days": (end - start).days + 1,
        "gaps": gaps,
        "gap_count": len(gaps),
    }


def prune_raw_csvs(
    raw_dir: str | Path,
    *,
    keep_days: int,
    also_prune_by_source: bool = True,
) -> Dict[str, int]:
    """Delete combined raw CSVs older than ``keep_days`` (by filename date)."""
    if keep_days <= 0:
        return {"deleted_combined": 0, "deleted_by_source": 0}
    root = Path(raw_dir)
    cutoff = date.today() - timedelta(days=keep_days)
    deleted_combined = 0
    deleted_by_source = 0
    for path in root.glob("raw_posts_*.csv"):
        m = _RAW_DATE_RE.match(path.name)
        if not m:
            continue
        d = date.fromisoformat(m.group(1))
        if d < cutoff:
            path.unlink(missing_ok=True)
            deleted_combined += 1
    if also_prune_by_source:
        by_src = root / "by_source"
        if by_src.is_dir():
            for path in by_src.glob("raw_posts_*_*.csv"):
                parts = path.stem.split("_")
                if len(parts) >= 3:
                    try:
                        d = date.fromisoformat(parts[2])
                    except ValueError:
                        continue
                    if d < cutoff:
                        path.unlink(missing_ok=True)
                        deleted_by_source += 1
    return {
        "deleted_combined": deleted_combined,
        "deleted_by_source": deleted_by_source,
    }


def append_crawl_journal(
    journal_path: str | Path,
    entry: Dict[str, Any],
) -> Path:
    path = Path(journal_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(entry)
    row.setdefault("recorded_at", datetime.now().isoformat())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def run_collect_persist(
    config_path: str,
    trade_date: str,
    *,
    skip_crawl: bool = False,
    journal_path: str = "data/raw/crawl_journal.jsonl",
    prune_keep_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Best-effort daily collect + persist raw CSV; journal either way."""
    from opinion_trading.agents.workflow import OpinionTradingWorkflow
    from opinion_trading.core.config_loader import load_runtime_config

    runtime = load_runtime_config(config_path)
    raw_dir = runtime.raw_dir
    result: Dict[str, Any] = {
        "trade_date": trade_date,
        "raw_dir": raw_dir,
        "ok": False,
        "mode": "collect-persist",
    }
    workflow = OpinionTradingWorkflow(config_path=config_path)
    run_d = datetime.strptime(trade_date, "%Y-%m-%d").date()
    try:
        out = workflow.run_daily(run_d, skip_crawl=skip_crawl)
        result["ok"] = True
        result["signals"] = out.get("signals")
        result["raw_csv"] = out.get("raw_csv")
        result["skip_crawl"] = skip_crawl
    except Exception as exc:
        logger.warning("collect-persist primary run failed: %s", exc)
        result["error"] = str(exc)
        if not skip_crawl:
            try:
                out = workflow.run_daily(run_d, skip_crawl=True)
                result["ok"] = True
                result["fallback_fast_daily"] = True
                result["raw_csv"] = out.get("raw_csv")
            except Exception as exc2:
                result["fallback_error"] = str(exc2)
    span = summarize_raw_span(raw_dir)
    result["span"] = span
    if prune_keep_days is not None and prune_keep_days > 0:
        result["prune"] = prune_raw_csvs(raw_dir, keep_days=prune_keep_days)
    append_crawl_journal(
        journal_path,
        {
            "trade_date": trade_date,
            "ok": result.get("ok"),
            "skip_crawl": skip_crawl,
            "raw_csv": result.get("raw_csv"),
            "gap_count": span.get("gap_count"),
        },
    )
    return result


def format_span_report(summary: Dict[str, Any]) -> str:
    lines = [
        f"raw_dir: {summary.get('raw_dir')}",
        f"files: {summary.get('count', 0)}",
        f"first: {summary.get('first')}",
        f"last: {summary.get('last')}",
        f"gaps ({summary.get('gap_count', 0)}): "
        + ", ".join((summary.get("gaps") or [])[:12]),
    ]
    if summary.get("gap_count", 0) > 12:
        lines.append("  ... (truncated)")
    return "\n".join(lines)
