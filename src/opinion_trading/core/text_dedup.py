"""Cross-post deduplication for raw sentiment rows (mitigate repost / copy-paste noise)."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Tuple


def _normalize_text(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\u4e00-\u9fff]+", "", t)
    return t[:2000]


def content_fingerprint(row: Dict[str, Any]) -> str:
    title = str(row.get("title") or "")
    content = str(row.get("content") or row.get("text") or "")
    platform = str(row.get("platform") or "")
    symbol = str(row.get("symbol") or "")
    blob = f"{symbol}|{platform}|{_normalize_text(title)}|{_normalize_text(content)}"
    return hashlib.sha256(blob.encode("utf-8", errors="ignore")).hexdigest()[:32]


def dedupe_raw_rows(
    rows: List[Dict[str, Any]],
    *,
    keep: str = "first",
) -> Tuple[List[Dict[str, Any]], int]:
    """Return deduped rows and count of removed duplicates."""
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    removed = 0
    iterable = reversed(rows) if keep == "last" else rows
    for row in iterable:
        fp = content_fingerprint(row)
        if fp in seen:
            removed += 1
            continue
        seen.add(fp)
        if keep == "last":
            out.insert(0, row)
        else:
            out.append(row)
    return out, removed