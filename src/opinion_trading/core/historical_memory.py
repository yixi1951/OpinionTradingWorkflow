"""Filtered recall over JSONL memory stores (offline, read-only)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from opinion_trading.core.memory_store import JsonLineMemoryStore
from opinion_trading.core.models import MemoryRecallConfig, TradeSignal

MEMORY_KIND_FILES: Dict[str, str] = {
    "signals": "signal_history.jsonl",
    "sentiment": "sentiment_history.jsonl",
    "trades": "trade_history.jsonl",
    "events": "event_log.jsonl",
    "quality_gate": "quality_gate_history.jsonl",
}

KNOWN_KINDS = tuple(sorted(MEMORY_KIND_FILES.keys()))


def _parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    if len(text) >= 10:
        text = text[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _row_trade_date(row: Mapping[str, Any]) -> Optional[date]:
    for key in ("trade_date", "date"):
        parsed = _parse_iso_date(row.get(key))
        if parsed is not None:
            return parsed
    for key in ("ts", "timestamp"):
        parsed = _parse_iso_date(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _row_symbol(row: Mapping[str, Any]) -> Optional[str]:
    sym = row.get("symbol")
    if sym:
        return str(sym).strip()
    payload = row.get("payload")
    if isinstance(payload, dict):
        ps = payload.get("symbol")
        if ps:
            return str(ps).strip()
    return None


def memory_has_history(memory_dir: str) -> bool:
    root = Path(memory_dir)
    for name in MEMORY_KIND_FILES.values():
        path = root / name
        if path.is_file() and path.stat().st_size > 0:
            return True
    return False


def load_memory_recall_config(raw: Optional[Mapping[str, Any]]) -> MemoryRecallConfig:
    mem = dict(raw or {})
    return MemoryRecallConfig(
        recall_enabled=bool(mem.get("recall_enabled", False)),
        recall_auto=bool(mem.get("recall_auto", False)),
        lookback_days=int(mem.get("lookback_days", 14)),
        prune_keep_days=int(mem.get("prune_keep_days", 0)),
    )


def resolve_recall_enabled(
    memory_dir: str,
    cfg: Optional[MemoryRecallConfig],
) -> bool:
    env = os.environ.get("MEMORY_RECALL", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    if cfg is None:
        return False
    if cfg.recall_enabled:
        return True
    if cfg.recall_auto and memory_has_history(memory_dir):
        return True
    return False


def query_memory(
    memory_dir: str,
    *,
    kind: str,
    symbol: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Return matching JSONL rows newest-first (up to ``limit``)."""
    key = kind.strip().lower()
    file_name = MEMORY_KIND_FILES.get(key)
    if file_name is None:
        raise ValueError(f"Unknown memory kind {kind!r}; expected one of {KNOWN_KINDS}")

    start = _parse_iso_date(start_date) if start_date else None
    end = _parse_iso_date(end_date) if end_date else None
    sym_filter = symbol.strip().upper() if symbol else None
    cap = max(1, int(limit))

    store = JsonLineMemoryStore(memory_dir)
    rows = store.read_all(file_name)
    matched: List[Dict[str, Any]] = []
    for row in rows:
        row_sym = _row_symbol(row)
        if sym_filter and (not row_sym or row_sym.upper() != sym_filter):
            continue
        row_date = _row_trade_date(row)
        if start and row_date and row_date < start:
            continue
        if end and row_date and row_date > end:
            continue
        if start and row_date is None and key != "quality_gate":
            continue
        matched.append(dict(row))

    def sort_key(item: Dict[str, Any]) -> tuple:
        d = _row_trade_date(item)
        ts = str(item.get("ts") or item.get("timestamp") or "")
        return (d or date.min, ts)

    matched.sort(key=sort_key, reverse=True)
    return matched[:cap]


def recall_symbol_context(
    memory_dir: str,
    symbol: str,
    *,
    lookback_days: int = 14,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Compact per-symbol summary for agents / scoring context injection."""
    sym = symbol.strip().upper()
    today = as_of or date.today()
    window_start = today - timedelta(days=max(1, int(lookback_days)))
    start_s = window_start.isoformat()
    end_s = today.isoformat()

    sentiment_rows = query_memory(
        memory_dir,
        kind="sentiment",
        symbol=sym,
        start_date=start_s,
        end_date=end_s,
        limit=500,
    )
    signal_rows = query_memory(
        memory_dir,
        kind="signals",
        symbol=sym,
        start_date=start_s,
        end_date=end_s,
        limit=50,
    )
    trade_rows = query_memory(
        memory_dir,
        kind="trades",
        symbol=sym,
        start_date=start_s,
        end_date=end_s,
        limit=50,
    )
    event_rows = query_memory(
        memory_dir,
        kind="events",
        symbol=sym,
        start_date=start_s,
        end_date=end_s,
        limit=80,
    )

    scores = [
        float(r["sentiment_score"])
        for r in sentiment_rows
        if r.get("sentiment_score") is not None
    ]
    platform_buckets: Dict[str, List[float]] = {}
    for row in sentiment_rows:
        plat = str(row.get("platform") or "unknown")
        val = row.get("sentiment_score")
        if val is None:
            continue
        platform_buckets.setdefault(plat, []).append(float(val))
    platform_avg = {
        plat: round(mean(vals), 4) for plat, vals in platform_buckets.items()
    }

    last_sent = sentiment_rows[0] if sentiment_rows else None
    last_signal = signal_rows[0] if signal_rows else None
    last_trade = trade_rows[0] if trade_rows else None

    event_types = [str(e.get("event_type") or "") for e in event_rows[:12]]

    return {
        "symbol": sym,
        "lookback_days": int(lookback_days),
        "window_start": start_s,
        "window_end": end_s,
        "sentiment": {
            "row_count": len(sentiment_rows),
            "avg_score": round(mean(scores), 4) if scores else None,
            "last_trade_date": (
                _row_trade_date(last_sent).isoformat()
                if last_sent and _row_trade_date(last_sent)
                else None
            ),
            "platform_avg": platform_avg,
        },
        "signals": {
            "count": len(signal_rows),
            "last": _compact_signal(last_signal),
        },
        "trades": {
            "count": len(trade_rows),
            "last": _compact_trade(last_trade),
        },
        "events": {
            "count": len(event_rows),
            "recent_types": [t for t in event_types if t],
        },
    }


def _compact_signal(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "trade_date": row.get("trade_date"),
        "action": row.get("action"),
        "confidence": row.get("confidence"),
        "reason": (str(row.get("reason") or "")[:160]),
    }


def _compact_trade(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "trade_date": row.get("trade_date"),
        "action": row.get("action"),
        "shares": row.get("shares"),
        "price": row.get("price"),
        "note": (str(row.get("note") or "")[:120]),
    }


def format_recall_snippet(recall: Mapping[str, Any], *, lang: str = "zh") -> str:
    sent = recall.get("sentiment") or {}
    sig = recall.get("signals") or {}
    tr = recall.get("trades") or {}
    avg = sent.get("avg_score")
    avg_txt = f"{avg:+.3f}" if avg is not None else "n/a"
    if lang.startswith("zh"):
        return (
            f"历史记忆({recall.get('lookback_days')}d): "
            f"情感均值{avg_txt}({sent.get('row_count', 0)}条); "
            f"最近信号{sig.get('count', 0)}; 纸面成交{tr.get('count', 0)}"
        )
    return (
        f"memory({recall.get('lookback_days')}d): "
        f"sentiment avg {avg_txt} ({sent.get('row_count', 0)} rows); "
        f"signals {sig.get('count', 0)}; paper fills {tr.get('count', 0)}"
    )


def apply_recall_to_signals(
    signals: Sequence[TradeSignal],
    symbol_recall: Optional[Mapping[str, Mapping[str, Any]]],
    *,
    lang: str = "zh",
) -> None:
    if not symbol_recall:
        return
    for sig in signals:
        ctx = symbol_recall.get(sig.symbol.upper()) or symbol_recall.get(sig.symbol)
        if not ctx:
            continue
        snippet = format_recall_snippet(ctx, lang=lang)
        if sig.explanation:
            sig.explanation = f"{sig.explanation}\n{snippet}"
        else:
            sig.explanation = snippet


def build_symbol_recall_map(
    memory_dir: str,
    symbols: Iterable[str],
    *,
    lookback_days: int,
    as_of: date,
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for sym in symbols:
        key = str(sym).strip().upper()
        if not key or key in out:
            continue
        out[key] = recall_symbol_context(
            memory_dir,
            key,
            lookback_days=lookback_days,
            as_of=as_of,
        )
    return out


def prune_memory_jsonl(
    memory_dir: str,
    *,
    keep_days: int,
    kinds: Optional[Sequence[str]] = None,
) -> Dict[str, int]:
    """Drop rows older than ``keep_days`` (by trade_date). Returns deleted counts."""
    if keep_days <= 0:
        return {}
    cutoff = date.today() - timedelta(days=keep_days)
    selected = list(kinds) if kinds else list(MEMORY_KIND_FILES.keys())
    deleted: Dict[str, int] = {}
    store = JsonLineMemoryStore(memory_dir)
    for kind in selected:
        file_name = MEMORY_KIND_FILES.get(kind)
        if not file_name:
            continue
        path = Path(memory_dir) / file_name
        if not path.is_file():
            deleted[kind] = 0
            continue
        rows = store.read_all(file_name)
        kept: List[Dict[str, Any]] = []
        removed = 0
        for row in rows:
            row_date = _row_trade_date(row)
            if row_date is not None and row_date < cutoff:
                removed += 1
                continue
            kept.append(row)
        if removed:
            _rewrite_jsonl(path, kept)
        deleted[kind] = removed
    return deleted


def _rewrite_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        tmp_path.replace(path)
    finally:
        if tmp_path.exists() and not path.exists():
            tmp_path.unlink(missing_ok=True)


def format_query_table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "(no rows)"
    lines = ["trade_date\tsymbol\tsummary"]
    for row in rows:
        d = _row_trade_date(row) or ""
        sym = _row_symbol(row) or ""
        summary_bits = []
        for key in (
            "action",
            "event_type",
            "sentiment_score",
            "confidence",
            "overall_pass",
        ):
            if key in row and row[key] is not None:
                summary_bits.append(f"{key}={row[key]}")
        lines.append(f"{d}\t{sym}\t{'; '.join(summary_bits)}")
    return "\n".join(lines)
