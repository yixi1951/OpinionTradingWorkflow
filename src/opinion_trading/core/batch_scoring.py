"""Chunked offline batch scoring helper (keyword / hybrid structure; no live parallel LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


@dataclass
class BatchScoringConfig:
    enabled: bool = False
    chunk_size: int = 12
    mode: str = "keyword"  # keyword | hybrid


def load_batch_scoring_config(raw: Optional[dict] = None) -> BatchScoringConfig:
    import os

    pipe = (raw or {}).get("ai_pipeline", {}) or {}
    block = pipe.get("batch_scoring", {}) or {}
    env_on = os.environ.get("BATCH_SCORING", "").strip().lower()
    enabled = bool(block.get("enabled", False))
    if env_on in ("1", "true", "yes", "on"):
        enabled = True
    elif env_on in ("0", "false", "no", "off"):
        enabled = False
    chunk = int(block.get("chunk_size", pipe.get("max_screen_batch", 12)))
    return BatchScoringConfig(
        enabled=enabled,
        chunk_size=max(1, chunk),
        mode=str(block.get("mode", "keyword")).lower(),
    )


def _chunk(items: Sequence[Any], size: int) -> List[List[Any]]:
    size = max(1, int(size))
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def score_texts_keyword(texts: Sequence[str]) -> List[float]:
    from opinion_trading.services.llm_gateway import _keyword_scores

    return [float(s) for s in _keyword_scores(list(texts))]


def score_texts_hybrid_offline(texts: Sequence[str]) -> List[float]:
    """Offline hybrid = keyword only (LLM weight applied when live keys exist elsewhere)."""
    return score_texts_keyword(texts)


def batch_score_texts(
    texts: Sequence[str],
    *,
    config: BatchScoringConfig,
    scorer: Optional[Callable[[Sequence[str]], List[float]]] = None,
) -> Tuple[List[float], Dict[str, int]]:
    """Score texts in chunks; returns flat scores + stats."""
    if not texts:
        return [], {"chunks": 0, "rows": 0}
    if scorer is None:
        if config.mode == "hybrid":
            scorer = score_texts_hybrid_offline
        else:
            scorer = score_texts_keyword
    if not config.enabled:
        scores = scorer(texts)
        return scores, {"chunks": 1, "rows": len(texts)}

    all_scores: List[float] = []
    chunks = _chunk(texts, config.chunk_size)
    for batch in chunks:
        all_scores.extend(scorer(batch))
    return all_scores, {"chunks": len(chunks), "rows": len(texts)}


def apply_batch_scores_to_rows(
    rows: List[Dict[str, Any]],
    *,
    config: BatchScoringConfig,
    text_key: str = "content",
    score_key: str = "keyword_score",
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Fill ``score_key`` on rows using chunked offline scoring."""
    texts = [
        str(r.get(text_key) or r.get("summary") or r.get("title") or "") for r in rows
    ]
    scores, stats = batch_score_texts(texts, config=config)
    if len(scores) != len(rows):
        return rows, {**stats, "error": 1}
    out: List[Dict[str, Any]] = []
    for row, sc in zip(rows, scores):
        new_row = dict(row)
        new_row[score_key] = float(sc)
        new_row["score_source"] = config.mode if config.enabled else row.get(
            "score_source", "existing"
        )
        out.append(new_row)
    return out, stats
