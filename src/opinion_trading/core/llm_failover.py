"""Live-LLM failover after Jev: DeepSeek → Qwen (OpenAI-compatible) → keyword.

``AISentimentAnalyzer`` tries TypeSafe Jev first (see ``jev_client``), then
calls ``score_texts_with_failover`` for DeepSeek/Qwen. CI keeps
``SCORING_MODE=keyword`` and no API keys, so pytest never hits the network.
One structured warning is logged when a live provider fails and the next hop
is used (Qwen or keyword).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from opinion_trading.core.deepseek_client import (
    DeepSeekSettings,
    live_llm_requested,
    load_deepseek_settings,
    score_texts_deepseek,
)
from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

QWEN_DEFAULT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_DEFAULT_MODEL = "qwen-turbo"

# Module-level latch so a burst of row scores logs one warning.
_FAILOVER_LOGGED = False


def reset_failover_log() -> None:
    global _FAILOVER_LOGGED
    _FAILOVER_LOGGED = False


def qwen_fallback_enabled() -> bool:
    raw = os.environ.get("LLM_QWEN_FALLBACK")
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() not in {"0", "false", "no"}


def load_qwen_settings() -> Optional[DeepSeekSettings]:
    """OpenAI-compatible Qwen/DashScope settings, or None if no key."""
    key = (
        os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or ""
    ).strip()
    if not key:
        return None
    base = (os.environ.get("QWEN_BASE_URL") or QWEN_DEFAULT_BASE).strip() or QWEN_DEFAULT_BASE
    model = (os.environ.get("QWEN_MODEL") or QWEN_DEFAULT_MODEL).strip() or QWEN_DEFAULT_MODEL
    try:
        timeout = float(os.environ.get("QWEN_TIMEOUT") or os.environ.get("DEEPSEEK_TIMEOUT", "30") or 30)
    except ValueError:
        timeout = 30.0
    return DeepSeekSettings(
        api_key=key,
        base_url=base.rstrip("/"),
        model=model,
        timeout=max(1.0, timeout),
    )


def live_providers() -> List[Tuple[str, DeepSeekSettings]]:
    """Ordered optional live backends. Empty in CI (no keys)."""
    out: List[Tuple[str, DeepSeekSettings]] = []
    ds = load_deepseek_settings()
    if ds.configured:
        out.append(("deepseek", ds))
    if qwen_fallback_enabled():
        qw = load_qwen_settings()
        if qw is not None:
            out.append(("qwen", qw))
    return out


def any_live_key() -> bool:
    return bool(live_providers())


def _scrub(text: str) -> str:
    out = str(text or "")
    for name in ("DEEPSEEK_API_KEY", "QWEN_API_KEY", "DASHSCOPE_API_KEY"):
        key = (os.environ.get(name) or "").strip()
        if key and key in out:
            out = out.replace(key, "***")
    return out[:240]


def log_failover_warning(
    *,
    failed: Sequence[str],
    used: str,
    reason: str,
) -> None:
    """Emit at most one structured warning per process burst."""
    global _FAILOVER_LOGGED
    if _FAILOVER_LOGGED:
        return
    _FAILOVER_LOGGED = True
    payload: Dict[str, Any] = {
        "event": "llm_failover",
        "failed": [str(x) for x in failed],
        "used": used,
        "reason": _scrub(reason),
    }
    logger.warning("LLM_FAILOVER %s", json.dumps(payload, ensure_ascii=False))


def score_texts_with_failover(
    texts: Sequence[str],
) -> Optional[Tuple[str, List[float]]]:
    """Try DeepSeek then Qwen. Returns (provider, scores) or None → keyword.

    Does nothing when live LLM is not requested or no keys are set.
    """
    texts_list = [str(t or "") for t in texts]
    if not texts_list:
        return ("keyword", [])
    if not live_llm_requested():
        return None

    providers = live_providers()
    if not providers:
        return None

    failed: List[str] = []
    last_reason = ""
    for name, settings in providers:
        try:
            scores = score_texts_deepseek(texts_list, settings=settings)
        except Exception as exc:
            failed.append(name)
            last_reason = f"{type(exc).__name__}: {exc}"
            logger.debug("%s live scoring failed: %s", name, _scrub(str(exc)))
            continue
        if len(scores) != len(texts_list):
            failed.append(name)
            last_reason = "score length mismatch"
            continue
        if failed:
            log_failover_warning(failed=failed, used=name, reason=last_reason)
        return name, scores

    log_failover_warning(failed=failed, used="keyword", reason=last_reason or "all live providers failed")
    return None
