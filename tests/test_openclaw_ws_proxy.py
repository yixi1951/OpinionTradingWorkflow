from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import openclaw_ws_proxy as proxy  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPENCLAW_PROXY_KEYWORD_ONLY", "1")
    monkeypatch.delenv("WS_GATEWAY_TOKEN", raising=False)
    return TestClient(proxy.app)


def test_health_and_ready_endpoints(client):
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert "requests" in body

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_sentiment_keyword_only_returns_scores(client):
    response = client.post(
        "/api/v1/sentiment",
        json={"texts": ["业绩超预期，强烈看好", "风险很大建议回避"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert "scores" in body
    assert len(body["scores"]) == 2
    assert all(isinstance(x, (int, float)) for x in body["scores"])
    assert body["scores"][0] > body["scores"][1]
    assert body.get("source") == "keyword_fallback"


def test_fallback_scores_bullish_vs_bearish():
    scores = proxy._fallback_scores(["涨停利好", "跌停暴跌"])
    assert scores[0] > 0.1
    assert scores[1] < -0.1


def test_normalize_scores():
    assert proxy._normalize_scores([0.5, -0.2]) == [0.5, -0.2]
    assert proxy._normalize_scores("bad") is None
