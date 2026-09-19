"""Optional semantic near-duplicate filter (char-shingle Jaccard; no ML deps)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from opinion_trading.core.text_dedup import content_fingerprint


@dataclass
class SemanticNearDedupConfig:
    enabled: bool = False
    method: str = "jaccard"  # jaccard | simhash
    jaccard_threshold: float = 0.85
    simhash_hamming_max: int = 3
    shingle_size: int = 3


def load_semantic_near_dedup_config(
    raw: Optional[dict] = None,
) -> SemanticNearDedupConfig:
    import os

    coll = (raw or {}).get("collection", {}) or {}
    block = coll.get("semantic_near_dedup", {}) or {}
    env_on = os.environ.get("SEMANTIC_NEAR_DEDUP", "").strip().lower()
    enabled = bool(block.get("enabled", False))
    if env_on in ("1", "true", "yes", "on"):
        enabled = True
    elif env_on in ("0", "false", "no", "off"):
        enabled = False
    return SemanticNearDedupConfig(
        enabled=enabled,
        method=str(block.get("method", "jaccard")).lower(),
        jaccard_threshold=float(block.get("jaccard_threshold", 0.85)),
        simhash_hamming_max=int(block.get("simhash_hamming_max", 3)),
        shingle_size=max(2, int(block.get("shingle_size", 3))),
    )


def _normalize_text(row: Dict[str, Any]) -> str:
    title = str(row.get("title") or "")
    body = str(row.get("content") or row.get("summary") or "")
    blob = f"{title} {body}".lower()
    blob = re.sub(r"\s+", " ", blob).strip()
    return blob


def char_shingles(text: str, k: int) -> set[str]:
    text = re.sub(r"\s+", "", text)
    if len(text) < k:
        return {text} if text else set()
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def simhash64(text: str, k: int = 3) -> int:
    """Simple 64-bit SimHash over char shingles."""
    shingles = char_shingles(text, k)
    if not shingles:
        return 0
    bits = [0] * 64
    for sh in shingles:
        digest = hashlib.md5(sh.encode("utf-8")).digest()
        h = int.from_bytes(digest[:8], "big")
        for i in range(64):
            bits[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i, v in enumerate(bits):
        if v >= 0:
            out |= 1 << i
    return out


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def dedupe_near_semantic(
    rows: List[Dict[str, Any]],
    *,
    config: SemanticNearDedupConfig,
    keep: str = "first",
) -> Tuple[List[Dict[str, Any]], int]:
    """Drop rows that are near-duplicates of an earlier row in the batch."""
    if not config.enabled or not rows:
        return rows, 0
    kept: List[Dict[str, Any]] = []
    shingles_cache: List[set[str]] = []
    simhash_cache: List[int] = []
    removed = 0
    method = config.method if config.method in ("jaccard", "simhash") else "jaccard"

    for row in rows:
        text = _normalize_text(row)
        if not text:
            kept.append(row)
            shingles_cache.append(set())
            simhash_cache.append(0)
            continue
        sh = char_shingles(text, config.shingle_size)
        sh_hash = simhash64(text, config.shingle_size)
        is_dup = False
        for idx, prev_sh in enumerate(shingles_cache):
            if method == "simhash":
                if hamming_distance(sh_hash, simhash_cache[idx]) <= config.simhash_hamming_max:
                    is_dup = True
                    break
            else:
                if jaccard_similarity(sh, prev_sh) >= config.jaccard_threshold:
                    is_dup = True
                    break
        if is_dup:
            removed += 1
            if keep == "last":
                # replace last kept row with same fingerprint bucket — skip for simplicity
                continue
            continue
        kept.append(row)
        shingles_cache.append(sh)
        simhash_cache.append(sh_hash)
    return kept, removed


def row_semantic_fingerprint(row: Dict[str, Any], *, shingle_size: int = 3) -> str:
    """Stable fingerprint combining exact + simhash hex (for tests / logging)."""
    base = content_fingerprint(row)
    text = _normalize_text(row)
    sh = simhash64(text, shingle_size)
    return f"{base}:{sh:016x}"
