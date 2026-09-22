from __future__ import annotations

import json

import pytest
import requests

from opinion_trading.core.ai_sentiment import AISentimentAnalyzer
from opinion_trading.core.jev_client import (
    SENTIMENT_QUESTION,
    jev_index_to_scalar,
    parse_sentiment_answer,
    score_texts_jev,
)
from opinion_trading.core.scoring_cascade import live_scoring_providers, parse_scoring_provider_chain


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


def _jev_payload(score: float, confidence: float = 0.92) -> dict:
    return {
        "model": "jev-1.13.0",
        "answers": {
            SENTIMENT_QUESTION: {
                "type": "score",
                "score": score,
                "confidence": confidence,
                "probabilities": {"0": 0.0, "4": 1.0},
            }
        },
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def test_jev_index_to_scalar_mapping():
    assert jev_index_to_scalar(0.0) == pytest.approx(-1.0)
    assert jev_index_to_scalar(4.0) == pytest.approx(1.0)
    assert jev_index_to_scalar(2.0) == pytest.approx(0.0)
    assert jev_index_to_scalar(3.0) == pytest.approx(0.5)


def test_parse_sentiment_answer():
    scalar, conf = parse_sentiment_answer(_jev_payload(4.0))
    assert scalar == pytest.approx(1.0)
    assert conf == pytest.approx(0.92)


def test_provider_chain_from_env(monkeypatch):
    monkeypatch.setenv("SCORING_PROVIDER", "jev,deepseek,keyword")
    assert parse_scoring_provider_chain() == ["jev", "deepseek", "keyword"]
    assert live_scoring_providers() == ["jev", "deepseek"]


def test_analyzer_jev_success(monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts-test-key")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")
    seen = []

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.append(url)
        assert headers["Authorization"] == "Bearer ts-test-key"
        assert json["questions"][SENTIMENT_QUESTION]["type"] == "score"
        return _Resp(_jev_payload(4.0))

    monkeypatch.setattr("opinion_trading.core.jev_client.requests.post", fake_post)
    analyzer = AISentimentAnalyzer(enable_fusion=False)
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["龙头主升浪，强烈看多加仓"])
    assert results[0].source == "jev"
    assert results[0].score == pytest.approx(1.0)
    assert "typesafe" in seen[0]


def test_analyzer_jev_fail_falls_back_to_deepseek(monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts-test-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    monkeypatch.setenv("DEEPSEEK_RETRY_SLEEP", "0")
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")

    def fake_jev_post(url, headers=None, json=None, timeout=None):
        raise requests.Timeout("jev slow")

    def fake_ds_post(url, headers=None, json=None, timeout=None):
        return _Resp(
            {"choices": [{"message": {"content": '{"scores": [0.33]}'}}]}
        )

    monkeypatch.setattr("opinion_trading.core.jev_client.requests.post", fake_jev_post)
    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post", fake_ds_post
    )
    analyzer = AISentimentAnalyzer(enable_fusion=False)
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["业绩略超预期"])
    assert results[0].source == "deepseek"
    assert results[0].score == pytest.approx(0.33)


def test_analyzer_low_jev_confidence_failover(monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts-test-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    monkeypatch.setenv("DEEPSEEK_RETRY_SLEEP", "0")
    monkeypatch.setenv("JEV_MIN_CONFIDENCE", "0.5")
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")

    monkeypatch.setattr(
        "opinion_trading.core.jev_client.requests.post",
        lambda *a, **k: _Resp(_jev_payload(4.0, confidence=0.2)),
    )
    monkeypatch.setattr(
        "opinion_trading.core.deepseek_client.requests.post",
        lambda *a, **k: _Resp(
            {"choices": [{"message": {"content": '{"scores": [-0.2]}'}}]}
        ),
    )
    analyzer = AISentimentAnalyzer(enable_fusion=False)
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["观望震荡"])
    assert results[0].source == "deepseek"


def test_no_live_keys_keyword_only(monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")

    def fail_net(*a, **k):
        raise AssertionError("network must not be called without keys")

    monkeypatch.setattr("opinion_trading.core.jev_client.requests.post", fail_net)
    monkeypatch.setattr("opinion_trading.core.deepseek_client.requests.post", fail_net)
    analyzer = AISentimentAnalyzer(enable_fusion=False)
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["利好上涨突破，看多买入"])
    assert results[0].source == "keyword"
    assert results[0].score > 0


def test_score_texts_jev_mocked(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts-test")
    monkeypatch.setattr(
        "opinion_trading.core.jev_client.requests.post",
        lambda *a, **k: _Resp(_jev_payload(0.0)),
    )
    pairs = score_texts_jev(["暴跌踩雷"])
    assert pairs[0][0] == pytest.approx(-1.0)
