"""SQLite-backed fingerprint store for cross-day near-duplicate raw posts."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from opinion_trading.core.models import CrossDayDedupConfig
from opinion_trading.core.text_dedup import content_fingerprint


def load_cross_day_dedup_config(
    raw: Optional[Dict[str, Any]] = None,
) -> CrossDayDedupConfig:
    import os

    coll = (raw or {}).get("collection", {}) or {}
    block = coll.get("cross_day_dedup", {}) or {}
    env_on = os.environ.get("CROSS_DAY_DEDUP", "").strip().lower()
    enabled = bool(block.get("enabled", False))
    if env_on in ("1", "true", "yes", "on"):
        enabled = True
    elif env_on in ("0", "false", "no", "off"):
        enabled = False
    return CrossDayDedupConfig(
        enabled=enabled,
        db_path=str(block.get("db_path", "data/memory/cross_day_fingerprints.sqlite")),
        lookback_days=int(block.get("lookback_days", 30)),
    )


class CrossDayFingerprintStore:
    """Persist content fingerprints across trading days (offline SQLite)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fingerprints (
                    fp TEXT PRIMARY KEY,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 1
                )
                """
            )

    def has_recent(self, fp: str, *, as_of: date, lookback_days: int) -> bool:
        cutoff = (as_of - timedelta(days=max(0, lookback_days))).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_seen FROM fingerprints WHERE fp = ? AND last_seen >= ?",
                (fp, cutoff),
            ).fetchone()
        return row is not None

    def register_many(self, fps: List[str], trade_date: date) -> int:
        if not fps:
            return 0
        day = trade_date.isoformat()
        inserted = 0
        with self._connect() as conn:
            for fp in fps:
                cur = conn.execute(
                    """
                    INSERT INTO fingerprints (fp, first_seen, last_seen, hit_count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(fp) DO UPDATE SET
                        last_seen = excluded.last_seen,
                        hit_count = hit_count + 1
                    """,
                    (fp, day, day),
                )
                if cur.rowcount == 1:
                    inserted += 1
        return inserted

    def purge_before(self, cutoff: date) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM fingerprints WHERE last_seen < ?",
                (cutoff.isoformat(),),
            )
            return int(cur.rowcount or 0)


def filter_cross_day_duplicates(
    rows: List[Dict[str, Any]],
    *,
    store: CrossDayFingerprintStore,
    trade_date: date,
    lookback_days: int,
) -> Tuple[List[Dict[str, Any]], int]:
    """Drop rows whose fingerprint was seen within lookback_days."""
    kept: List[Dict[str, Any]] = []
    removed = 0
    for row in rows:
        fp = content_fingerprint(row)
        if store.has_recent(fp, as_of=trade_date, lookback_days=lookback_days):
            removed += 1
            continue
        kept.append(row)
    return kept, removed


def apply_cross_day_dedup(
    rows: List[Dict[str, Any]],
    *,
    trade_date: date,
    config: CrossDayDedupConfig,
    store: Optional[CrossDayFingerprintStore] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Filter then register surviving fingerprints for the trade_date."""
    stats = {"removed": 0, "registered": 0}
    if not config.enabled or not rows:
        return rows, stats
    st = store or CrossDayFingerprintStore(config.db_path)
    filtered, removed = filter_cross_day_duplicates(
        rows,
        store=st,
        trade_date=trade_date,
        lookback_days=config.lookback_days,
    )
    stats["removed"] = removed
    fps = [content_fingerprint(r) for r in filtered]
    stats["registered"] = st.register_many(fps, trade_date)
    return filtered, stats
