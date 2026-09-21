"""Dashboard API routes (memory, eval, auth)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    root = tmp_path / "memory"
    root.mkdir()
    row = {
        "trade_date": "2026-06-17",
        "symbol": "600519",
        "platform": "guba",
        "sentiment_score": 0.42,
    }
    (root / "sentiment_history.jsonl").write_text(
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return root


def test_memory_and_sentiment_endpoints(memory_dir: Path, monkeypatch):
    monkeypatch.setenv("MEMORY_DIR", str(memory_dir))
    from opinion_trading.services import api_app

    client = TestClient(api_app.app)
    kinds = client.get("/v1/memory/kinds").json()
    assert "sentiment" in kinds["kinds"]

    q = client.get("/v1/memory/query", params={"kind": "sentiment", "limit": 10}).json()
    assert q["ok"] is True
    assert q["count"] == 1

    hist = client.get("/v1/sentiment/history").json()
    assert hist["count"] == 1
    assert hist["avg_score"] == 0.42

    recall = client.get("/v1/memory/recall", params={"symbol": "600519"}).json()
    assert recall["ok"] is True
    assert recall["recall"]["symbol"] == "600519"


def test_auth_verify_optional(monkeypatch):
    monkeypatch.delenv("STREAMLIT_DASHBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    from opinion_trading.services import api_app

    client = TestClient(api_app.app)
    body = client.post("/v1/auth/verify", json={"password": "x"}).json()
    assert body["required"] is False
    assert body["ok"] is True


def test_auth_verify_password(monkeypatch):
    monkeypatch.setenv("STREAMLIT_DASHBOARD_PASSWORD", "secret")
    from opinion_trading.services import api_app

    client = TestClient(api_app.app)
    bad = client.post("/v1/auth/verify", json={"password": "nope"}).json()
    assert bad["required"] is True
    assert bad["ok"] is False
    good = client.post("/v1/auth/verify", json={"password": "secret"}).json()
    assert good["ok"] is True
