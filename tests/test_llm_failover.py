from __future__ import annotations

import json

import pytest
import requests

from opinion_trading.core.ai_sentiment import AISentimentAnalyzer
from opinion_trading.core.deepseek_client import DeepSeekSettings
from opinion_trading.core.llm_failover import (
    live_providers,
    load_qwen_settings,
    log_failover_warning,
    reset_failover_log,
    score_texts_with_failover,
)


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code}")
            err.response = self
            raise err

    def json(self):
        return self._payload


def _chat_payload(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_qwen_settings_from_either_env(monkeypatch):
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-dash-test")
    settings = load_qwen_settings()
    assert settings is not None
    assert settings.api_key == "sk-dash-test"
    assert "dashscope" in settings.base_url
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("QWEN_API_KEY", "sk-qwen-test")
    assert load_qwen_settings().api_key == "sk-qwen-test"


def test_live_providers_empty_without_keys(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    assert live_providers() == []
    monkeypatch.setenv("SCORING_MODE", "ai")
    assert score_texts_with_failover(["看多"]) is None


def test_deepseek_fail_falls_back_to_qwen(monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    monkeypatch.setenv("QWEN_API_KEY", "sk-qw-test")
    monkeypatch.setenv("DEEPSEEK_RETRY_SLEEP", "0")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    reset_failover_log()
    seen = []

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.append(url)
        if "deepseek" in url:
            raise requests.ConnectionError("deepseek down")
        return _Resp(_chat_payload('{"scores": [0.42]}'))

    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post", fake_post
    )
    outcome = score_texts_with_failover(["业绩超预期"])
    assert outcome is not None
    provider, scores = outcome
    assert provider == "qwen"
    assert scores == [0.42]
    assert any("deepseek" in u for u in seen)
    assert any("dashscope" in u for u in seen)


def test_deepseek_fail_without_qwen_returns_none_and_one_warning(monkeypatch, caplog):
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_RETRY_SLEEP", "0")
    reset_failover_log()

    def fake_post(url, headers=None, json=None, timeout=None):
        raise requests.ConnectionError("deepseek down")

    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post", fake_post
    )
    with caplog.at_level("WARNING"):
        assert score_texts_with_failover(["暴跌"]) is None
        log_failover_warning(failed=["deepseek"], used="keyword", reason="again")
    warnings = [r.message for r in caplog.records if "LLM_FAILOVER" in r.message]
    assert len(warnings) == 1
    payload = json.loads(warnings[0].split("LLM_FAILOVER ", 1)[1])
    assert payload["event"] == "llm_failover"
    assert payload["used"] == "keyword"
    assert "deepseek" in payload["failed"]
    assert "sk-ds-test" not in warnings[0]


def test_keyword_mode_skips_live_even_with_keys(monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "keyword")
    monkeypatch.delenv("HYBRID_USE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    monkeypatch.setenv("QWEN_API_KEY", "sk-qw-test")
    called = {"n": 0}

    def fake_post(*a, **k):
        called["n"] += 1
        raise AssertionError("network should not be used in keyword mode")

    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post", fake_post
    )
    assert score_texts_with_failover(["看多"]) is None
    assert called["n"] == 0


def test_analyzer_qwen_source_after_deepseek_fail(monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    monkeypatch.setenv("QWEN_API_KEY", "sk-qw-test")
    monkeypatch.setenv("DEEPSEEK_RETRY_SLEEP", "0")
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")
    reset_failover_log()

    def fake_post(url, headers=None, json=None, timeout=None):
        if "deepseek" in (url or ""):
            raise requests.Timeout("ds timeout")
        return _Resp(_chat_payload('{"scores": [-0.5]}'))

    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post", fake_post
    )
    analyzer = AISentimentAnalyzer(enable_fusion=False)
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["建议卖出观望"])
    assert results[0].source == "qwen"
    assert results[0].score == pytest.approx(-0.5)


def test_analyzer_keyword_after_all_live_fail(monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    monkeypatch.setenv("DEEPSEEK_RETRY_SLEEP", "0")
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    reset_failover_log()
    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post",
        lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("down")),
    )
    analyzer = AISentimentAnalyzer(enable_fusion=False)
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["利好上涨突破，看多买入"])
    assert results[0].source == "keyword"
    assert results[0].score > 0


def test_qwen_disabled_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds")
    monkeypatch.setenv("QWEN_API_KEY", "sk-qw")
    monkeypatch.setenv("LLM_QWEN_FALLBACK", "0")
    names = [n for n, _ in live_providers()]
    assert names == ["deepseek"]
    assert isinstance(live_providers()[0][1], DeepSeekSettings)
