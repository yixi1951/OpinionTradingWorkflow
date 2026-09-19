from __future__ import annotations

import json

import pytest
import requests

from opinion_trading.core.deepseek_client import (
    MissingDeepSeekKeyError,
    SAMPLE_TEXTS,
    chat_completions_url,
    deepseek_configured,
    live_llm_requested,
    missing_key_message,
    probe_deepseek,
    redact_secret,
    run_cli,
    score_sample,
    score_texts_deepseek,
)
from opinion_trading.core.ai_sentiment import AISentimentAnalyzer


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


def test_chat_completions_url_adds_v1():
    assert (
        chat_completions_url("https://api.deepseek.com")
        == "https://api.deepseek.com/v1/chat/completions"
    )
    assert (
        chat_completions_url("https://api.deepseek.com/v1")
        == "https://api.deepseek.com/v1/chat/completions"
    )


def test_not_configured_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert deepseek_configured() is False
    with pytest.raises(MissingDeepSeekKeyError) as exc:
        score_texts_deepseek(["看多"])
    msg = str(exc.value)
    assert "DEEPSEEK_API_KEY" in msg
    assert "未配置" in msg
    out = probe_deepseek()
    assert out["status"] == "NOT_CONFIGURED"
    assert out["ok"] is False
    assert out["configured"] is False


def test_redact_secret_does_not_echo_key():
    assert "sk-live-secret" not in redact_secret("sk-live-secret-value")
    assert redact_secret("") == ""


def test_live_llm_requested_respects_keyword_mode(monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "keyword")
    monkeypatch.delenv("HYBRID_USE_LLM", raising=False)
    assert live_llm_requested() is False
    monkeypatch.setenv("HYBRID_USE_LLM", "1")
    assert live_llm_requested() is True
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("HYBRID_USE_LLM", "0")
    assert live_llm_requested() is True


def test_score_texts_mocked_http(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["auth"] = (headers or {}).get("Authorization", "")
        seen["payload"] = json
        return _Resp(_chat_payload('{"scores": [0.8, -0.6]}'))

    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post", fake_post
    )
    scores = score_texts_deepseek(["买入看多", "暴跌卖出"])
    assert scores == [0.8, -0.6]
    assert seen["url"].endswith("/v1/chat/completions")
    assert seen["auth"] == "Bearer sk-test-not-real"
    # logs / public dicts must not dump the raw key
    public = probe_deepseek()
    assert "sk-test-not-real" not in json.dumps(public)


def test_retry_once_on_connection_error(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("DEEPSEEK_RETRY_SLEEP", "0")
    calls = {"n": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("down")
        return _Resp(_chat_payload('{"scores": [0.1]}'))

    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post", fake_post
    )
    assert score_texts_deepseek(["中性"]) == [0.1]
    assert calls["n"] == 2


def test_analyzer_uses_deepseek_when_key_present(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")
    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post",
        lambda *a, **k: _Resp(_chat_payload('{"scores": [0.91]}')),
    )
    analyzer = AISentimentAnalyzer(enable_fusion=False)
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["业绩超预期维持买入"])
    assert results[0].source == "deepseek"
    assert results[0].score == pytest.approx(0.91)


def test_analyzer_require_key_raises(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("DEEPSEEK_REQUIRE", "1")
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    analyzer = AISentimentAnalyzer(enable_fusion=False)
    analyzer.openclaw = None
    with pytest.raises(MissingDeepSeekKeyError):
        analyzer.analyze_texts(["看多"])


def test_analyzer_falls_back_to_keyword_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("DEEPSEEK_REQUIRE", "0")
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")
    analyzer = AISentimentAnalyzer(enable_fusion=False)
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["利好上涨突破，看多买入"])
    assert results[0].source == "keyword"
    assert results[0].score > 0


def test_cli_not_configured_exit_codes(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert run_cli(["--json"]) == 2
    assert run_cli(["--soft", "--json"]) == 0
    assert run_cli(["--score-sample", "--soft"]) == 0


def test_score_sample_mocked(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-real")
    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post",
        lambda *a, **k: _Resp(_chat_payload('{"scores": [0.5, -0.4, 0.0]}')),
    )
    out = score_sample()
    assert out["ok"] is True
    assert out["scores"] == [0.5, -0.4, 0.0]
    assert len(out["texts"]) == len(SAMPLE_TEXTS)
    assert "sk-test-not-real" not in json.dumps(out)


def test_missing_key_message_bilingual():
    msg = missing_key_message()
    assert "DEEPSEEK_API_KEY" in msg
    assert "未配置" in msg


def test_main_accepts_deepseek_modes(monkeypatch):
    import sys
    from opinion_trading import main as main_module

    monkeypatch.setattr(sys, "argv", ["prog", "--mode", "deepseek-probe"])
    args = main_module.parse_args()
    assert args.mode == "deepseek-probe"
    monkeypatch.setattr(sys, "argv", ["prog", "--mode", "score-sample"])
    assert main_module.parse_args().mode == "score-sample"
