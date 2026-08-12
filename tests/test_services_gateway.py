"""Service-layer tests: gateway cache/failover, prompts, FastAPI apps."""

from __future__ import annotations


import pytest
from fastapi.testclient import TestClient


def test_prompt_registry_versions_and_activate(tmp_path, monkeypatch):
    from opinion_trading.services.prompt_registry import PromptRegistry

    # use real config/prompts if present
    reg = PromptRegistry("config/prompts")
    versions = reg.list_versions("sentiment")
    assert any(v["version"] == "v1" for v in versions)
    # v2 may exist
    if any(v["version"] == "v2" for v in versions):
        reg.set_active("sentiment", "v2")
        assert reg.get("sentiment").version == "v2"
        reg.set_active("sentiment", "v1")
        assert reg.get("sentiment").version == "v1"


def test_gateway_keyword_fallback_and_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEYS_STORE_PATH", str(tmp_path / "api_keys.json"))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_GATEWAY_URL", raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    monkeypatch.setenv("ALLOW_KEYWORD_FALLBACK", "1")

    from opinion_trading.core.api_key_store import reset_api_key_store_singleton
    from opinion_trading.services.llm_gateway import MultiModelGateway

    reset_api_key_store_singleton()
    gw = MultiModelGateway()
    texts = ["强烈看好突破上涨", "暴跌利空风险"]
    r1 = gw.score(texts, use_cache=True)
    assert len(r1["scores"]) == 2
    assert r1["scores"][0] > r1["scores"][1]
    assert r1["provider"] == "keyword_fallback"
    assert r1["cache_hit"] is False

    r2 = gw.score(texts, use_cache=True)
    assert r2["cache_hit"] is True
    assert r2["provider"] == "cache"
    assert r2["scores"] == r1["scores"]
    stats = gw.stats()
    assert stats["cache_hits"] >= 1


def test_circuit_opens_after_failures(monkeypatch):
    from opinion_trading.services.llm_gateway import CircuitState

    c = CircuitState()
    assert c.allow()
    c.record_failure(threshold=2, cooldown_sec=30)
    assert c.allow()
    c.record_failure(threshold=2, cooldown_sec=30)
    assert not c.allow()
    c.record_success()
    assert c.allow()


def test_inference_app_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEYS_STORE_PATH", str(tmp_path / "api_keys.json"))
    monkeypatch.setenv("ALLOW_KEYWORD_FALLBACK", "1")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_GATEWAY_URL", raising=False)
    from opinion_trading.core.api_key_store import reset_api_key_store_singleton
    from opinion_trading.services import inference_app

    reset_api_key_store_singleton()
    client = TestClient(inference_app.app)
    assert client.get("/health").json()["status"] == "ok"
    body = client.post(
        "/api/v1/sentiment", json={"texts": ["利好上涨", "利空下跌"]}
    ).json()
    assert "scores" in body
    assert len(body["scores"]) == 2
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "inference_requests_total" in metrics.text


def test_api_status_degraded_when_backends_down(monkeypatch):
    monkeypatch.setenv("COLLECTOR_URL", "http://127.0.0.1:59991")
    monkeypatch.setenv("INFERENCE_URL", "http://127.0.0.1:59992")
    monkeypatch.setenv("COMPUTE_URL", "http://127.0.0.1:59993")
    from opinion_trading.services import api_app

    client = TestClient(api_app.app)
    st = client.get("/v1/status").json()
    assert st["api"] == "ok"
    assert st["collector"]["status"] == "down"


def test_scheduler_jobs_callable(monkeypatch):
    calls = []

    class FakeClient:
        def post(self, path, payload):
            calls.append((path, payload))
            return {"ok": True}

    monkeypatch.setattr(
        "opinion_trading.services.clients.collector_client", lambda: FakeClient()
    )
    monkeypatch.setattr(
        "opinion_trading.services.clients.compute_client", lambda: FakeClient()
    )
    from opinion_trading.services.scheduler import (
        create_scheduler,
        job_postmarket_factors,
        job_premarket_signals,
    )

    job_premarket_signals()
    job_postmarket_factors()
    assert any("/v1/collect" in c[0] for c in calls)
    assert any("/v1/compute/daily" in c[0] for c in calls)
    assert any("/v1/compute/factors" in c[0] for c in calls)

    try:
        sched = create_scheduler()
        assert sched.get_job("premarket_signals") is not None
        assert sched.get_job("postmarket_factors") is not None
    except SystemExit:
        pytest.skip("apscheduler not installed")
