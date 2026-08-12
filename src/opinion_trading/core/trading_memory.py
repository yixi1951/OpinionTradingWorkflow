"""Cross-day trading memory: prior sentiment for signals + per-symbol cards."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from opinion_trading.core.memory_store import JsonLineMemoryStore
from opinion_trading.core.models import (
    AggregatedSentiment,
    OpinionSnapshot,
    TradeSignal,
)


def _parse_trade_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def row_to_snapshot(row: Dict[str, Any]) -> Optional[OpinionSnapshot]:
    """Convert a sentiment_history JSONL row into OpinionSnapshot."""
    trade_date = _parse_trade_date(row.get("trade_date"))
    symbol = str(row.get("symbol") or "").strip()
    platform = str(row.get("platform") or "").strip()
    if not trade_date or not symbol or not platform:
        return None
    try:
        score = float(row.get("sentiment_score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    try:
        post_count = int(row.get("post_count", 0) or 0)
    except (TypeError, ValueError):
        post_count = 0
    ts_raw = row.get("timestamp")
    if isinstance(ts_raw, datetime):
        ts = ts_raw
    elif ts_raw:
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except ValueError:
            ts = datetime.now()
    else:
        ts = datetime.now()
    return OpinionSnapshot(
        timestamp=ts,
        trade_date=trade_date,
        platform=platform,
        symbol=symbol,
        sentiment_score=score,
        post_count=post_count,
        source=str(row.get("source") or "memory"),
    )


def load_prior_snapshots(
    store: JsonLineMemoryStore,
    *,
    before: date,
    symbols: Optional[Sequence[str]] = None,
    lookback_days: int = 60,
    file_name: str = "sentiment_history.jsonl",
) -> List[OpinionSnapshot]:
    """
    Load historical platform snapshots strictly before ``before``.

    Dedupes to the latest record per (trade_date, symbol, platform) so re-runs
    of the same day do not inflate aggregates.
    """
    lookback_days = max(1, int(lookback_days))
    earliest = before - timedelta(days=lookback_days)
    symbol_set = {str(s) for s in symbols} if symbols else None

    latest: Dict[tuple, OpinionSnapshot] = {}
    for row in store.read_all(file_name):
        snap = row_to_snapshot(row)
        if snap is None:
            continue
        if snap.trade_date >= before or snap.trade_date < earliest:
            continue
        if symbol_set is not None and snap.symbol not in symbol_set:
            continue
        key = (snap.trade_date.isoformat(), snap.symbol, snap.platform)
        prev = latest.get(key)
        if prev is None or snap.timestamp >= prev.timestamp:
            latest[key] = snap

    return sorted(
        latest.values(),
        key=lambda s: (s.trade_date, s.symbol, s.platform),
    )


def merge_snapshots_with_memory(
    today_snapshots: Sequence[OpinionSnapshot],
    prior_snapshots: Sequence[OpinionSnapshot],
) -> List[OpinionSnapshot]:
    """Prior first, then today — analyst needs both dates for reversal logic."""
    return list(prior_snapshots) + list(today_snapshots)


def _avg(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def update_symbol_memory(
    memory_dir: str | Path,
    *,
    trade_date: date,
    aggregated_today: Dict[str, AggregatedSentiment],
    signals: Sequence[TradeSignal],
    prior_day_count: int = 0,
    file_name: str = "symbol_memory.json",
) -> Dict[str, Any]:
    """
    Upsert compact per-symbol memory cards used by the dashboard / reports.

    Stores rolling score, streak vs prior card, and last signal action.
    """
    path = Path(memory_dir) / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: Dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded.get("symbols", loaded) if "symbols" in loaded else loaded
                if not isinstance(existing, dict):
                    existing = {}
        except (json.JSONDecodeError, OSError):
            existing = {}

    signal_by_symbol = {s.symbol: s for s in signals}
    now_iso = datetime.now().isoformat(timespec="seconds")

    for symbol, agg in aggregated_today.items():
        score = float(agg.average_score)
        platforms = {
            str(p): round(float(v), 4) for p, v in sorted(agg.platform_scores.items())
        }
        prev = existing.get(symbol) if isinstance(existing.get(symbol), dict) else {}
        prev_score = float(prev.get("last_score", 0.0) or 0.0) if prev else 0.0
        prev_streak = int(prev.get("streak", 0) or 0) if prev else 0
        if score > 0.05 and prev_score > 0.05:
            streak = prev_streak + 1 if prev_streak > 0 else 1
        elif score < -0.05 and prev_score < -0.05:
            streak = prev_streak - 1 if prev_streak < 0 else -1
        elif abs(score) <= 0.05:
            streak = 0
        else:
            streak = 1 if score > 0 else -1

        sig = signal_by_symbol.get(symbol)
        note_parts = [
            f"均分 {score:+.3f}",
            f"平台 {len(platforms)}",
        ]
        if prior_day_count:
            note_parts.append(f"回看 {prior_day_count} 日记忆")
        if sig:
            note_parts.append(f"信号 {sig.action}@{sig.confidence:.2f}")

        existing[symbol] = {
            "symbol": symbol,
            "last_trade_date": trade_date.isoformat(),
            "last_score": round(score, 4),
            "prev_score": round(prev_score, 4),
            "delta": round(score - prev_score, 4),
            "streak": streak,
            "platforms": platforms,
            "last_action": sig.action if sig else (prev.get("last_action") if prev else None),
            "last_confidence": (
                round(float(sig.confidence), 4)
                if sig
                else (prev.get("last_confidence") if prev else None)
            ),
            "last_reason": sig.reason if sig else (prev.get("last_reason") if prev else ""),
            "updated_at": now_iso,
            "note": " · ".join(note_parts),
        }

    payload = {
        "updated_at": now_iso,
        "as_of": trade_date.isoformat(),
        "prior_days_used": int(prior_day_count),
        "symbols": existing,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return payload


def load_symbol_memory(
    memory_dir: str | Path, file_name: str = "symbol_memory.json"
) -> Dict[str, Any]:
    path = Path(memory_dir) / file_name
    if not path.exists():
        return {"symbols": {}, "updated_at": None, "as_of": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"symbols": {}, "updated_at": None, "as_of": None}
    if not isinstance(data, dict):
        return {"symbols": {}, "updated_at": None, "as_of": None}
    symbols = data.get("symbols")
    if not isinstance(symbols, dict):
        symbols = {k: v for k, v in data.items() if isinstance(v, dict) and "last_score" in v}
    return {
        "updated_at": data.get("updated_at"),
        "as_of": data.get("as_of"),
        "prior_days_used": data.get("prior_days_used"),
        "symbols": symbols,
    }


def symbol_memory_as_rows(memory: Dict[str, Any]) -> List[Dict[str, Any]]:
    symbols = memory.get("symbols") or {}
    rows: List[Dict[str, Any]] = []
    for sym, card in symbols.items():
        if not isinstance(card, dict):
            continue
        rows.append(
            {
                "symbol": card.get("symbol") or sym,
                "last_trade_date": card.get("last_trade_date"),
                "last_score": card.get("last_score"),
                "delta": card.get("delta"),
                "streak": card.get("streak"),
                "last_action": card.get("last_action"),
                "last_confidence": card.get("last_confidence"),
                "note": card.get("note"),
            }
        )
    rows.sort(key=lambda r: (r.get("last_score") is None, -(r.get("last_score") or 0.0)))
    return rows


def prior_date_count(snapshots: Sequence[OpinionSnapshot]) -> int:
    return len({s.trade_date for s in snapshots})


def load_prior_from_raw_dir(
    raw_dir: str | Path,
    *,
    before: date,
    symbols: Optional[Sequence[str]] = None,
    lookback_days: int = 60,
) -> List[OpinionSnapshot]:
    """
    Rebuild prior snapshots from partitioned raw_posts_YYYY-MM-DD.csv files.

    Useful when sentiment_history.jsonl is thin but multi-date raw already exists.
    """
    from opinion_trading.core.snapshot_from_raw import snapshots_from_raw_rows

    root = Path(raw_dir)
    if not root.exists():
        return []
    lookback_days = max(1, int(lookback_days))
    earliest = before - timedelta(days=lookback_days)
    symbol_set = {str(s) for s in symbols} if symbols else None
    out: List[OpinionSnapshot] = []

    for path in sorted(root.glob("raw_posts_*.csv")):
        stem = path.stem  # raw_posts_2026-05-13
        parts = stem.split("_")
        if len(parts) < 3:
            continue
        td = _parse_trade_date(parts[-1])
        if td is None or td >= before or td < earliest:
            continue
        try:
            import csv

            with path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        except OSError:
            continue
        snaps = snapshots_from_raw_rows(rows, td, recency_enabled=False)
        for snap in snaps:
            if symbol_set is not None and snap.symbol not in symbol_set:
                continue
            out.append(snap)
    return out


def prefer_history_then_raw(
    history: Sequence[OpinionSnapshot],
    from_raw: Sequence[OpinionSnapshot],
) -> List[OpinionSnapshot]:
    """Prefer JSONL memory rows; fill missing (date,symbol,platform) from raw."""
    latest: Dict[tuple, OpinionSnapshot] = {}
    for snap in from_raw:
        key = (snap.trade_date.isoformat(), snap.symbol, snap.platform)
        latest[key] = snap
    for snap in history:
        key = (snap.trade_date.isoformat(), snap.symbol, snap.platform)
        latest[key] = snap
    return sorted(
        latest.values(),
        key=lambda s: (s.trade_date, s.symbol, s.platform),
    )
