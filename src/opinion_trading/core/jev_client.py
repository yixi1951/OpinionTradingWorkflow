"""TypeSafe Jev (/v1/systemone) client for A-share social sentiment.

Maps a single multi-level ``score`` question to scalar sentiment in ``[-1, 1]``.

Score rubric (5 levels, indices 0..4):
  0 strongly bearish → -1.0
  1 bearish          → -0.5
  2 neutral          →  0.0
  3 bullish          → +0.5
  4 strongly bullish → +1.0

Jev returns a probability-weighted mean index ``s`` in ``[0, n-1]``; we linearly
map ``s`` to ``2 * s / (n - 1) - 1`` and clamp to ``[-1, 1]``.

One POST per post text (``state``); all questions are evaluated in one round trip.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

from opinion_trading.core.deepseek_client import live_llm_requested
from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

DEFAULT_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
SENTIMENT_QUESTION = "equity_sentiment"
NUM_LEVELS = 5

_A_SHARE_SENTIMENT_CRITERIA = [
    "强烈看空：明确看跌、建议卖出、暴跌踩雷、崩盘止损等极端悲观表述",
    "偏空：利空、风险加大、减仓、破位、看空等偏悲观表述",
    "中性：观望、震荡、无明确买卖方向，或仅复述事实",
    "偏多：利好、看多、买入、上涨预期、反弹等偏乐观表述",
    "强烈看多：强烈看涨、主升浪、龙头、超预期、加仓等极端乐观表述",
]


@dataclass(frozen=True)
class JevSettings:
    api_key: str
    url: str
    model: str
    timeout: float

    @property
    def configured(self) -> bool:
        return bool((self.api_key or "").strip())


def load_jev_settings() -> JevSettings:
    key = (
        os.environ.get("TYPESAFE_API_KEY")
        or os.environ.get("JEV_API_KEY")
        or ""
    ).strip()
    url = (os.environ.get("JEV_API_URL") or os.environ.get("TYPESAFE_API_URL") or DEFAULT_URL).strip()
    model = (
        os.environ.get("JEV_MODEL")
        or os.environ.get("TYPESAFE_MODEL")
        or DEFAULT_MODEL
    ).strip() or DEFAULT_MODEL
    try:
        timeout = float(
            os.environ.get("JEV_TIMEOUT")
            or os.environ.get("TYPESAFE_TIMEOUT", "30")
            or 30
        )
    except ValueError:
        timeout = 30.0
    return JevSettings(
        api_key=key,
        url=url.rstrip("/") if url else DEFAULT_URL,
        model=model,
        timeout=max(1.0, timeout),
    )


def jev_configured() -> bool:
    return load_jev_settings().configured


def jev_min_confidence() -> float:
    try:
        return float(os.environ.get("JEV_MIN_CONFIDENCE", "0.40") or 0.40)
    except ValueError:
        return 0.40


def jev_fallback_on_error() -> bool:
    raw = os.environ.get("JEV_FALLBACK")
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() not in {"0", "false", "no"}


def sentiment_questions() -> Dict[str, Any]:
    return {
        SENTIMENT_QUESTION: {
            "type": "score",
            "instructions": (
                "针对这条与中国A股相关的社交帖子，评估作者对标的股票的交易情绪"
                "方向与强度（忽略广告灌水，聚焦投资观点）。"
            ),
            "criteria": list(_A_SHARE_SENTIMENT_CRITERIA),
        }
    }


def jev_index_to_scalar(jev_score: float, num_levels: int = NUM_LEVELS) -> float:
    if num_levels < 2:
        return 0.0
    hi = float(num_levels - 1)
    x = max(0.0, min(hi, float(jev_score)))
    return max(-1.0, min(1.0, 2.0 * (x / hi) - 1.0))


def _retry_sleep() -> None:
    try:
        delay = float(os.environ.get("JEV_RETRY_SLEEP", "0.4") or 0)
    except ValueError:
        delay = 0.4
    if delay > 0:
        time.sleep(delay)


def _scrub(text: str) -> str:
    out = str(text or "")
    for name in ("TYPESAFE_API_KEY", "JEV_API_KEY"):
        key = (os.environ.get(name) or "").strip()
        if key and key in out:
            out = out.replace(key, "***")
    return out[:240]


def _post_systemone(
    *,
    state: str,
    settings: JevSettings,
    retries: int = 1,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.model,
        "state": state,
        "questions": sentiment_questions(),
    }
    last_exc: Optional[Exception] = None
    for attempt in range(max(1, retries + 1)):
        try:
            resp = requests.post(
                settings.url,
                headers=headers,
                json=body,
                timeout=settings.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise ValueError("jev response is not a JSON object")
            return data
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                _retry_sleep()
                continue
            raise exc
    raise RuntimeError(last_exc or "jev request failed")


def parse_sentiment_answer(
    payload: Dict[str, Any],
    *,
    num_levels: int = NUM_LEVELS,
) -> Tuple[float, float]:
    """Return (scalar in [-1,1], confidence)."""
    answers = payload.get("answers") or {}
    if not isinstance(answers, dict):
        raise ValueError("missing answers")
    block = answers.get(SENTIMENT_QUESTION)
    if not isinstance(block, dict):
        raise ValueError(f"missing question {SENTIMENT_QUESTION}")
    if str(block.get("type", "")).lower() != "score":
        raise ValueError("unexpected answer type")
    raw_score = block.get("score")
    if raw_score is None:
        raise ValueError("missing score field")
    conf_raw = block.get("confidence")
    confidence = float(conf_raw) if conf_raw is not None else 0.5
    scalar = jev_index_to_scalar(float(raw_score), num_levels=num_levels)
    return scalar, max(0.0, min(1.0, confidence))


def score_text_jev(
    text: str,
    *,
    settings: Optional[JevSettings] = None,
) -> Tuple[float, float]:
    settings = settings or load_jev_settings()
    if not settings.configured:
        raise RuntimeError("jev api key not configured")
    data = _post_systemone(state=str(text or ""), settings=settings)
    return parse_sentiment_answer(data)


def score_texts_jev(
    texts: Sequence[str],
    *,
    settings: Optional[JevSettings] = None,
) -> List[Tuple[float, float]]:
    """One systemone call per text; returns parallel (score, confidence) pairs."""
    settings = settings or load_jev_settings()
    if not settings.configured:
        raise RuntimeError("jev api key not configured")
    try:
        retries = int(os.environ.get("JEV_RETRIES", "1") or 1)
    except ValueError:
        retries = 1
    out: List[Tuple[float, float]] = []
    for text in texts:
        data = _post_systemone(
            state=str(text or ""),
            settings=settings,
            retries=max(0, retries),
        )
        out.append(parse_sentiment_answer(data))
    return out


def score_texts_jev_if_live(
    texts: Sequence[str],
) -> Optional[List[Tuple[float, float]]]:
    """No-op in keyword CI mode or without a key."""
    if not live_llm_requested():
        return None
    settings = load_jev_settings()
    if not settings.configured:
        return None
    try:
        return score_texts_jev(texts, settings=settings)
    except Exception as exc:
        if not jev_fallback_on_error():
            raise
        logger.debug("jev scoring failed: %s", _scrub(str(exc)))
        return None
