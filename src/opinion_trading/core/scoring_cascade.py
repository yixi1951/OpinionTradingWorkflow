"""Ordered live sentiment providers: Jev → DeepSeek (→ Qwen) → keyword fallback.

``keyword`` in config is handled by ``AISentimentAnalyzer``; this module only
returns the live AI hop order.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

_DEFAULT_LIVE_CHAIN = ("jev", "deepseek")
_KEYWORD_ALIASES = frozenset({"keyword", "lexicon", "offline"})


def _read_yaml_provider() -> str:
    path = Path(os.environ.get("OPINION_CONFIG", "config/settings.yaml"))
    if not path.is_file():
        return ""
    try:
        import yaml  # type: ignore

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.debug("could not read scoring.provider from %s: %s", path, exc)
        return ""
    scoring = raw.get("scoring") or {}
    provider = scoring.get("provider", "")
    if isinstance(provider, list):
        return ",".join(str(p) for p in provider)
    return str(provider or "").strip()


def parse_scoring_provider_chain() -> List[str]:
    """Full chain including keyword sentinel when present in config."""
    raw = (os.environ.get("SCORING_PROVIDER") or os.environ.get("SCORING_PROVIDERS") or "").strip()
    if not raw:
        raw = _read_yaml_provider()
    if not raw:
        raw = ",".join(_DEFAULT_LIVE_CHAIN) + ",keyword"
    parts = [p.strip().lower() for p in re.split(r"[,;]+", raw) if p.strip()]
    if not parts:
        parts = list(_DEFAULT_LIVE_CHAIN) + ["keyword"]
    if parts == ["jev"]:
        parts = ["jev", "deepseek", "keyword"]
    return parts


def live_scoring_providers() -> List[str]:
    """Live backends only, in failover order."""
    chain = parse_scoring_provider_chain()
    live = [p for p in chain if p not in _KEYWORD_ALIASES]
    if not live:
        return list(_DEFAULT_LIVE_CHAIN)
    return live
