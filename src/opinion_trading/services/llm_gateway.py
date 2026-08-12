"""Multi-provider LLM gateway with failover, circuit breaker + response cache."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import requests

from opinion_trading.core.log_utils import get_logger
from opinion_trading.core.storage import get_storage
from opinion_trading.services.prompt_registry import PromptRegistry

logger = get_logger(__name__)


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str
    enabled: bool = True


@dataclass
class CircuitState:
    failures: int = 0
    open_until: float = 0.0

    def allow(self) -> bool:
        return time.time() >= self.open_until

    def record_success(self) -> None:
        self.failures = 0
        self.open_until = 0.0

    def record_failure(self, threshold: int = 3, cooldown_sec: float = 60.0) -> None:
        self.failures += 1
        if self.failures >= threshold:
            self.open_until = time.time() + cooldown_sec
            logger.warning(
                "Circuit open for %ss after %s failures", cooldown_sec, self.failures
            )


def _load_providers() -> List[ProviderConfig]:
    providers: List[ProviderConfig] = []
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    ds_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    ds_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
    if ds_key:
        providers.append(
            ProviderConfig("deepseek", ds_url, ds_key, ds_model, enabled=True)
        )

    qw_key = os.environ.get(
        "QWEN_API_KEY", os.environ.get("DASHSCOPE_API_KEY", "")
    ).strip()
    qw_url = os.environ.get(
        "QWEN_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ).strip()
    qw_model = os.environ.get("QWEN_MODEL", "qwen-turbo").strip()
    if qw_key:
        providers.append(ProviderConfig("qwen", qw_url, qw_key, qw_model, enabled=True))

    gen_key = os.environ.get("LLM_FALLBACK_API_KEY", "").strip()
    gen_url = os.environ.get("LLM_FALLBACK_BASE_URL", "").strip()
    gen_model = os.environ.get("LLM_FALLBACK_MODEL", "gpt-4o-mini").strip()
    if gen_key and gen_url:
        providers.append(
            ProviderConfig("fallback_llm", gen_url, gen_key, gen_model, enabled=True)
        )

    oc_url = os.environ.get(
        "OPENCLAW_GATEWAY_URL", os.environ.get("OPENCLAW_URL", "")
    ).strip()
    # Avoid self-loop when this process IS the inference service on :8002
    if oc_url and ":8002" not in oc_url:
        providers.append(
            ProviderConfig(
                "openclaw",
                oc_url.rstrip("/"),
                os.environ.get("OPENCLAW_TOKEN", ""),
                os.environ.get("OPENCLAW_MODEL", "deepseek"),
                enabled=True,
            )
        )
    return providers


class SentimentCache:
    def __init__(self, ttl_seconds: int = 86400) -> None:
        self.ttl = ttl_seconds
        self.store = get_storage()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(texts: Sequence[str], scenario: str, version: str) -> str:
        payload = json.dumps(
            {"texts": list(texts), "scenario": scenario, "version": version},
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
        return f"llm:{scenario}:{version}:{digest}"

    def get(
        self, texts: Sequence[str], scenario: str, version: str
    ) -> Optional[List[float]]:
        key = self._key(texts, scenario, version)
        val = self.store.cache_get(key)
        if isinstance(val, list) and all(isinstance(x, (int, float)) for x in val):
            self.hits += 1
            return [float(x) for x in val]
        self.misses += 1
        return None

    def set(
        self, texts: Sequence[str], scenario: str, version: str, scores: List[float]
    ) -> None:
        key = self._key(texts, scenario, version)
        self.store.cache_set(key, scores, ttl_seconds=self.ttl)


def _keyword_scores(texts: Sequence[str]) -> List[float]:
    pos = ["上涨", "利好", "突破", "增长", "看多", "反弹", "盈利", "强势", "买入", "乐观"]
    neg = ["下跌", "利空", "风险", "暴跌", "看空", "回撤", "亏损", "弱势", "卖出", "悲观"]
    out = []
    for t in texts:
        p = sum(str(t).count(w) for w in pos)
        n = sum(str(t).count(w) for w in neg)
        s = (p - n) / (p + n + 5)
        out.append(max(-1.0, min(1.0, float(s))))
    return out


class MultiModelGateway:
    """Failover DeepSeek → Qwen → optional third → OpenClaw → keyword."""

    def __init__(self) -> None:
        self.prompts = PromptRegistry()
        self.cache = SentimentCache(
            ttl_seconds=int(os.environ.get("LLM_CACHE_TTL_SECONDS", "86400"))
        )
        self.fail_counts: Dict[str, int] = {}
        self.success_counts: Dict[str, int] = {}
        self.circuits: Dict[str, CircuitState] = {}
        self.circuit_threshold = int(os.environ.get("LLM_CIRCUIT_THRESHOLD", "3"))
        self.circuit_cooldown = float(os.environ.get("LLM_CIRCUIT_COOLDOWN_SEC", "60"))
        self._provider_gen = -1
        self._reload_providers(force=True)

    def _reload_providers(self, *, force: bool = False) -> None:
        """Refresh providers when encrypted API-key store generation changes."""
        try:
            from opinion_trading.core.api_key_store import (
                apply_runtime_key_overlay,
                runtime_key_generation,
            )

            apply_runtime_key_overlay()
            gen = int(runtime_key_generation())
        except Exception:
            gen = self._provider_gen if self._provider_gen >= 0 else 0
        if not force and gen == self._provider_gen:
            return
        self.providers = _load_providers()
        self._provider_gen = gen
        for p in self.providers:
            self.circuits.setdefault(p.name, CircuitState())

    def score(
        self,
        texts: List[str],
        *,
        scenario: str = "sentiment",
        prompt_version: Optional[str] = None,
        use_cache: bool = True,
        allow_keyword: Optional[bool] = None,
    ) -> Dict[str, Any]:
        self._reload_providers()
        texts = [str(t or "") for t in texts]
        prompt = self.prompts.get(scenario, prompt_version)
        version = prompt.version

        if use_cache:
            cached = self.cache.get(texts, scenario, version)
            if cached is not None and len(cached) == len(texts):
                return {
                    "scores": cached,
                    "provider": "cache",
                    "scenario": scenario,
                    "prompt_version": version,
                    "cache_hit": True,
                }

        errors: List[str] = []
        for provider in self.providers:
            if not provider.enabled:
                continue
            circuit = self.circuits.setdefault(provider.name, CircuitState())
            if not circuit.allow():
                errors.append(f"{provider.name}:circuit_open")
                continue
            try:
                scores = self._call_provider(provider, texts, scenario, version)
                if scores is None or len(scores) != len(texts):
                    raise RuntimeError("invalid score length")
                circuit.record_success()
                self.success_counts[provider.name] = (
                    self.success_counts.get(provider.name, 0) + 1
                )
                if use_cache:
                    self.cache.set(texts, scenario, version, scores)
                return {
                    "scores": scores,
                    "provider": provider.name,
                    "scenario": scenario,
                    "prompt_version": version,
                    "cache_hit": False,
                }
            except Exception as exc:
                circuit.record_failure(self.circuit_threshold, self.circuit_cooldown)
                self.fail_counts[provider.name] = (
                    self.fail_counts.get(provider.name, 0) + 1
                )
                errors.append(f"{provider.name}:{exc}")
                logger.warning("Provider %s failed: %s", provider.name, exc)
                continue

        if allow_keyword is None:
            allow_keyword = os.environ.get("ALLOW_KEYWORD_FALLBACK", "1").strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }
        if not allow_keyword:
            raise RuntimeError(
                "all LLM providers failed and keyword fallback is disabled: "
                + "; ".join(errors[:5])
            )

        scores = _keyword_scores(texts)
        if use_cache:
            self.cache.set(texts, scenario, version, scores)
        return {
            "scores": scores,
            "provider": "keyword_fallback",
            "scenario": scenario,
            "prompt_version": version,
            "cache_hit": False,
            "errors": errors[:5],
        }

    def _call_provider(
        self,
        provider: ProviderConfig,
        texts: List[str],
        scenario: str,
        version: str,
    ) -> Optional[List[float]]:
        if provider.name == "openclaw":
            url = provider.base_url.rstrip("/") + "/api/v1/sentiment"
            headers = {"Content-Type": "application/json"}
            if provider.api_key:
                headers["Authorization"] = f"Bearer {provider.api_key}"
            resp = requests.post(
                url, json={"texts": texts}, headers=headers, timeout=120
            )
            resp.raise_for_status()
            data = resp.json()
            scores = data.get("scores")
            if isinstance(scores, list):
                return [float(x) for x in scores]
            return None

        url = provider.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider.api_key}",
        }
        message = self.prompts.render(scenario, texts, version)
        payload = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": "You output strict JSON only."},
                {"role": "user", "content": message},
            ],
            "temperature": 0.0,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = (
            data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        return self._parse_scores(content, expected=len(texts))

    @staticmethod
    def _parse_scores(content: str, expected: int) -> Optional[List[float]]:
        text = str(content or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        try:
            obj = json.loads(text)
        except Exception:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                obj = json.loads(text[start : end + 1])
            except Exception:
                return None
        scores = obj.get("scores")
        if not isinstance(scores, list) or len(scores) != expected:
            return None
        return [max(-1.0, min(1.0, float(x))) for x in scores]

    def stats(self) -> Dict[str, Any]:
        total_hit = self.cache.hits
        total_miss = self.cache.misses
        hit_rate = total_hit / max(1, total_hit + total_miss)
        return {
            "providers": [p.name for p in self.providers],
            "success": self.success_counts,
            "failures": self.fail_counts,
            "circuits": {
                name: {
                    "failures": c.failures,
                    "open": not c.allow(),
                    "open_until": c.open_until,
                }
                for name, c in self.circuits.items()
            },
            "cache_hits": total_hit,
            "cache_misses": total_miss,
            "cache_hit_rate": hit_rate,
            "prompts": self.prompts.list_versions(),
        }
