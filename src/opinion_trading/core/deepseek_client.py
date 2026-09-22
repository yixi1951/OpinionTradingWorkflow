"""DeepSeek OpenAI-compatible client for live sentiment scoring.

Keys come from the environment / gitignored ``.env`` only — never from YAML.
CI and keyword mode do not call the network.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse

import requests

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
SAMPLE_TEXTS = (
    "贵州茅台业绩超预期，机构维持买入评级，继续看好龙头配置。",
    "暴跌风险加大，高估值难以为继，建议卖出观望。",
    "会议纪要仅复述财报数字，未给出明确买卖建议。",
)

_MISSING_KEY_ZH = (
    "未配置 DEEPSEEK_API_KEY，无法调用 DeepSeek 实时情绪打分。"
    "请在环境变量或 gitignore 的 .env 中设置密钥（见 .env.example），"
    "或使用 scoring.mode=keyword 离线关键词模式。"
)
_MISSING_KEY_EN = (
    "DEEPSEEK_API_KEY is not set; live DeepSeek sentiment scoring cannot run. "
    "Export the key (or put it in a gitignored .env; see .env.example), "
    "or use scoring.mode=keyword for the offline path."
)


class MissingDeepSeekKeyError(RuntimeError):
    """Live LLM was requested but no API key is configured."""

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message or missing_key_message())


def missing_key_message() -> str:
    return f"{_MISSING_KEY_ZH} / {_MISSING_KEY_EN}"


def _truthy(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes"}


def redact_secret(value: Optional[str]) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) <= 8:
        return "***"
    return f"{raw[:4]}…{raw[-2:]}"


def _scrub(text: str) -> str:
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    out = str(text or "")
    if key and key in out:
        out = out.replace(key, "***")
    return out[:240]


@dataclass(frozen=True)
class DeepSeekSettings:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout: float = 30.0

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def public_dict(self) -> Dict[str, Any]:
        return {
            "configured": self.configured,
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout,
            "api_key": redact_secret(self.api_key) if self.api_key else "",
        }


def load_deepseek_settings() -> DeepSeekSettings:
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    base = (os.environ.get("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model = (os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        timeout = float(os.environ.get("DEEPSEEK_TIMEOUT", "30") or 30)
    except ValueError:
        timeout = 30.0
    return DeepSeekSettings(
        api_key=key,
        base_url=base.rstrip("/"),
        model=model,
        timeout=max(1.0, timeout),
    )


def deepseek_configured() -> bool:
    return load_deepseek_settings().configured


def live_llm_requested() -> bool:
    """True when settings/env ask for a live LLM (not CI keyword mode)."""
    mode = str(os.environ.get("SCORING_MODE", "ai")).strip().lower()
    if mode in {
        "ai",
        "hybrid",
        "llm",
        "openclaw",
        "deepseek",
        "jev",
        "fuse",
        "fusion",
    }:
        return True
    return _truthy("HYBRID_USE_LLM", "0")


def deepseek_require_key() -> bool:
    return _truthy("DEEPSEEK_REQUIRE", "0")


def deepseek_fallback_on_error() -> bool:
    raw = os.environ.get("DEEPSEEK_FALLBACK")
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() not in {"0", "false", "no"}


def chat_completions_url(base_url: str) -> str:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def require_deepseek_key() -> DeepSeekSettings:
    settings = load_deepseek_settings()
    if not settings.configured:
        raise MissingDeepSeekKeyError()
    return settings


def _retry_sleep() -> None:
    try:
        delay = float(os.environ.get("DEEPSEEK_RETRY_SLEEP", "0.4") or 0)
    except ValueError:
        delay = 0.4
    if delay > 0:
        time.sleep(delay)


def _post_chat(
    *,
    messages: List[Dict[str, str]],
    settings: Optional[DeepSeekSettings] = None,
    temperature: float = 0.0,
    max_tokens: int = 256,
    retries: int = 1,
) -> Dict[str, Any]:
    settings = settings or require_deepseek_key()
    url = chat_completions_url(settings.base_url)
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    host = urlparse(url).netloc or url
    last_exc: Exception | None = None
    attempts = 1 + max(0, int(retries))
    for attempt in range(attempts):
        try:
            resp = requests.post(
                url, headers=headers, json=payload, timeout=settings.timeout
            )
            if resp.status_code in {429, 502, 503, 504} and attempt + 1 < attempts:
                logger.warning(
                    "DeepSeek HTTP %s from %s; retrying once", resp.status_code, host
                )
                _retry_sleep()
                continue
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise RuntimeError("DeepSeek response is not a JSON object")
            return data
        except requests.Timeout as exc:
            last_exc = exc
            logger.warning("DeepSeek timeout talking to %s (attempt %s)", host, attempt + 1)
            if attempt + 1 < attempts:
                _retry_sleep()
                continue
            raise
        except requests.ConnectionError as exc:
            last_exc = exc
            logger.warning("DeepSeek connection error to %s: %s", host, _scrub(str(exc)))
            if attempt + 1 < attempts:
                _retry_sleep()
                continue
            raise
        except requests.HTTPError as exc:
            last_exc = exc
            code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("DeepSeek HTTP error from %s: %s", host, code)
            raise
        except Exception as exc:
            last_exc = exc
            logger.warning("DeepSeek request failed: %s", _scrub(str(exc)))
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("DeepSeek request failed")


def chat_completion(
    user_content: str,
    *,
    system: str = "You output concise plain text.",
    settings: Optional[DeepSeekSettings] = None,
    temperature: float = 0.0,
    max_tokens: int = 64,
) -> str:
    data = _post_chat(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        settings=settings,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    )
    return str(content).strip()


def _parse_scores(content: str, expected: int) -> Optional[List[float]]:
    text = str(content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    obj: Any = None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                obj = None
        if obj is None:
            start, end = text.find("["), text.rfind("]")
            if start >= 0 and end > start:
                try:
                    obj = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    return None
    if isinstance(obj, list):
        scores = obj
    elif isinstance(obj, dict):
        scores = obj.get("scores")
    else:
        return None
    if not isinstance(scores, list) or len(scores) != expected:
        return None
    out: List[float] = []
    for item in scores:
        try:
            out.append(max(-1.0, min(1.0, float(item))))
        except (TypeError, ValueError):
            return None
    return out


def score_texts_deepseek(
    texts: Sequence[str],
    *,
    settings: Optional[DeepSeekSettings] = None,
) -> List[float]:
    """Call DeepSeek chat completions and parse ``{\"scores\": [...]}`` JSON."""
    texts_list = [str(t or "") for t in texts]
    if not texts_list:
        return []
    settings = settings or require_deepseek_key()
    user = (
        "Score each Chinese A-share social-media text in [-1, 1] "
        "(-1 bearish / 0 neutral / +1 bullish). "
        'Return STRICT JSON only: {"scores": [float, ...]} in the same order.\n'
        + json.dumps(texts_list, ensure_ascii=False)
    )
    content = chat_completion(
        user,
        system="You are a finance sentiment scorer. Output strict JSON only.",
        settings=settings,
        temperature=0.0,
        max_tokens=min(512, 48 + 24 * len(texts_list)),
    )
    parsed = _parse_scores(content, expected=len(texts_list))
    if parsed is None:
        raise RuntimeError("DeepSeek sentiment JSON could not be parsed")
    return parsed


def probe_deepseek() -> Dict[str, Any]:
    """Tiny live chat when a key is set; otherwise NOT CONFIGURED (no network)."""
    settings = load_deepseek_settings()
    public = settings.public_dict()
    if not settings.configured:
        return {
            "ok": False,
            "configured": False,
            "status": "NOT_CONFIGURED",
            "message": missing_key_message(),
            **public,
        }
    started = time.time()
    try:
        reply = chat_completion(
            "Reply with the single word pong.",
            system="Reply with one lowercase word only.",
            settings=settings,
            max_tokens=8,
        )
        latency_ms = int((time.time() - started) * 1000)
        ok = bool(reply)
        return {
            "ok": ok,
            "configured": True,
            "status": "OK" if ok else "EMPTY_REPLY",
            "message": "DeepSeek probe ok" if ok else "empty reply",
            "reply": reply[:80],
            "latency_ms": latency_ms,
            **public,
        }
    except Exception as exc:
        return {
            "ok": False,
            "configured": True,
            "status": "ERROR",
            "message": _scrub(str(exc)),
            "latency_ms": int((time.time() - started) * 1000),
            **public,
        }


def score_sample(
    texts: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    sample = list(texts) if texts is not None else list(SAMPLE_TEXTS)
    settings = load_deepseek_settings()
    public = settings.public_dict()
    if not settings.configured:
        return {
            "ok": False,
            "configured": False,
            "status": "NOT_CONFIGURED",
            "message": missing_key_message(),
            "texts": sample,
            "scores": [],
            **public,
        }
    try:
        scores = score_texts_deepseek(sample, settings=settings)
        return {
            "ok": True,
            "configured": True,
            "status": "OK",
            "message": "DeepSeek sample scores (research prototype, not a return forecast)",
            "texts": sample,
            "scores": scores,
            **public,
        }
    except Exception as exc:
        return {
            "ok": False,
            "configured": True,
            "status": "ERROR",
            "message": _scrub(str(exc)),
            "texts": sample,
            "scores": [],
            **public,
        }


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Probe DeepSeek or score a tiny Chinese fixture sample"
    )
    parser.add_argument(
        "--score-sample",
        action="store_true",
        help="Score 3 fixture posts instead of the ping probe",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument(
        "--soft",
        action="store_true",
        help="Exit 0 when NOT CONFIGURED (documented soft fail)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = score_sample() if args.score_sample else probe_deepseek()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = result.get("status", "")
        print(f"DEEPSEEK {status}")
        print(result.get("message", ""))
        if result.get("scores"):
            for text, score in zip(result.get("texts") or [], result["scores"]):
                print(f"  {score:+.3f}  {text[:60]}")
        elif result.get("reply"):
            print(f"reply={result['reply']}")
        model = result.get("model") or ""
        if result.get("configured"):
            print(f"model={model} base={result.get('base_url')}")
    if result.get("ok"):
        return 0
    if result.get("status") == "NOT_CONFIGURED":
        return 0 if args.soft else 2
    return 1
