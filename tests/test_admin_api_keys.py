"""Tests for admin API-key upload store + gateway overlay."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def key_store_env(tmp_path, monkeypatch):
    store_path = tmp_path / "api_keys.json"
    monkeypatch.setenv("API_KEYS_STORE_PATH", str(store_path))
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-admin-token")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENCLAW_TOKEN", raising=False)
    from opinion_trading.core.api_key_store import reset_api_key_store_singleton

    reset_api_key_store_singleton()
    yield store_path
    reset_api_key_store_singleton()
    os.environ.pop("DEEPSEEK_API_KEY", None)


def test_mask_secret_shapes():
    from opinion_trading.core.api_key_store import mask_secret

    assert mask_secret("sk-abcdefghijklmnop") == "sk-…mnop"
    assert mask_secret("plain-secret-value-9999") == "pl…9999"
    assert "plain-secret" not in mask_secret("plain-secret-value-9999")


def test_store_set_get_masked_clear(key_store_env, monkeypatch):
    from opinion_trading.core.api_key_store import (
        apply_runtime_key_overlay,
        get_api_key_store,
        mask_secret,
    )

    store = get_api_key_store(key_store_env)
    status = store.set_key("deepseek", "sk-test-key-ABCDEFGH1234", model="deepseek-chat")
    assert status["configured"] is True
    assert status["masked_key"] == mask_secret("sk-test-key-ABCDEFGH1234")
    assert "ABCDEFGH1234" not in status["masked_key"]
    assert status["model"] == "deepseek-chat"

    apply_runtime_key_overlay(store)
    assert os.environ.get("DEEPSEEK_API_KEY") == "sk-test-key-ABCDEFGH1234"
    assert os.environ.get("DEEPSEEK_MODEL") == "deepseek-chat"

    listed = store.list_status()
    ds = next(x for x in listed if x["provider"] == "deepseek")
    assert ds["masked_key"] == status["masked_key"]

    cleared = store.clear_key("deepseek")
    assert cleared["configured"] is False
    assert cleared["masked_key"] is None
    assert not (os.environ.get("DEEPSEEK_API_KEY") or "").strip()


def test_store_rejects_empty_key(key_store_env):
    from opinion_trading.core.api_key_store import get_api_key_store

    store = get_api_key_store(key_store_env)
    with pytest.raises(ValueError):
        store.set_key("deepseek", "   ")


def test_gateway_loads_uploaded_key(key_store_env, monkeypatch):
    monkeypatch.setenv("ALLOW_KEYWORD_FALLBACK", "0")
    monkeypatch.setenv("SCORING_MODE", "ai")
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_GATEWAY_URL", raising=False)

    from opinion_trading.core.api_key_store import get_api_key_store, reset_api_key_store_singleton
    from opinion_trading.services.llm_gateway import MultiModelGateway

    reset_api_key_store_singleton()
    store = get_api_key_store(key_store_env)
    store.set_key("deepseek", "sk-gateway-upload-KEY9999")

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=120):
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["json"] = json

        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": '{"scores":[0.5]}',
                            }
                        }
                    ]
                }

        return Resp()

    monkeypatch.setattr(
        "opinion_trading.services.llm_gateway.requests.post", fake_post
    )

    gw = MultiModelGateway()
    assert "deepseek" in [p.name for p in gw.providers]
    deepseek = next(p for p in gw.providers if p.name == "deepseek")
    assert deepseek.api_key == "sk-gateway-upload-KEY9999"

    result = gw.score(["利好"], use_cache=False, allow_keyword=False)
    assert result["provider"] == "deepseek"
    assert result["scores"] == [0.5]
    assert captured["headers"].get("Authorization") == "Bearer sk-gateway-upload-KEY9999"
    # ensure we never put full key into provider name / cache key path via stats
    stats = gw.stats()
    assert "KEY9999" not in str(stats.get("providers"))


def test_gateway_hot_reloads_after_upload(key_store_env, monkeypatch):
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_GATEWAY_URL", raising=False)
    from opinion_trading.core.api_key_store import get_api_key_store, reset_api_key_store_singleton
    from opinion_trading.services.llm_gateway import MultiModelGateway

    reset_api_key_store_singleton()
    gw = MultiModelGateway()
    assert "deepseek" not in [p.name for p in gw.providers]

    store = get_api_key_store(key_store_env)
    store.set_key("deepseek", "sk-hot-reload-AAAA1111")
    # score() should detect generation change
    monkeypatch.setenv("ALLOW_KEYWORD_FALLBACK", "1")

    def fake_post(url, json=None, headers=None, timeout=120):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": '{"scores":[0.1]}'}}]}

        return Resp()

    monkeypatch.setattr(
        "opinion_trading.services.llm_gateway.requests.post", fake_post
    )
    r = gw.score(["x"], use_cache=False, allow_keyword=False)
    assert r["provider"] == "deepseek"
    assert "deepseek" in [p.name for p in gw.providers]


def test_admin_http_set_status_clear(key_store_env, monkeypatch):
    # Re-import app after env is set so mount sees routes; store path via env
    from opinion_trading.core.api_key_store import reset_api_key_store_singleton
    from opinion_trading.services import api_app

    reset_api_key_store_singleton()
    client = TestClient(api_app.app)
    headers = {"Authorization": "Bearer test-admin-token"}

    denied = client.get("/v1/admin/keys")
    assert denied.status_code == 401

    listed = client.get("/v1/admin/keys", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert "providers" in body

    put = client.put(
        "/v1/admin/keys/deepseek",
        headers=headers,
        json={"api_key": "sk-http-upload-ZZZZ9999", "model": "deepseek-chat"},
    )
    assert put.status_code == 200
    put_body = put.json()
    assert put_body["ok"] is True
    assert put_body["configured"] is True
    assert put_body["masked_key"].endswith("9999")
    assert "ZZZZ9999" not in put_body["masked_key"] or put_body["masked_key"] == "sk-…9999"
    assert "sk-http-upload-ZZZZ9999" not in str(put_body)

    got = client.get("/v1/admin/keys/deepseek", headers=headers).json()
    assert got["configured"] is True
    assert got["masked_key"] == put_body["masked_key"]

    rotated = client.post(
        "/v1/admin/keys/deepseek/rotate",
        headers=headers,
        json={"api_key": "sk-rotated-YYYY8888"},
    )
    assert rotated.status_code == 200
    assert rotated.json()["action"] == "rotated"
    assert rotated.json()["masked_key"].endswith("8888")

    deleted = client.delete("/v1/admin/keys/deepseek", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["configured"] is False


def test_admin_requires_token_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEYS_STORE_PATH", str(tmp_path / "k.json"))
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    from opinion_trading.core.api_key_store import reset_api_key_store_singleton
    from opinion_trading.services import api_app

    reset_api_key_store_singleton()
    client = TestClient(api_app.app)
    r = client.get("/v1/admin/keys", headers={"Authorization": "Bearer x"})
    assert r.status_code == 503


def test_admin_rejects_empty_body(key_store_env):
    from opinion_trading.core.api_key_store import reset_api_key_store_singleton
    from opinion_trading.services import api_app

    reset_api_key_store_singleton()
    client = TestClient(api_app.app)
    headers = {"Authorization": "Bearer test-admin-token"}
    r = client.put(
        "/v1/admin/keys/deepseek",
        headers=headers,
        json={"api_key": ""},
    )
    assert r.status_code == 422
