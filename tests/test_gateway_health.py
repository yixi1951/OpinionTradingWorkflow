from __future__ import annotations

from types import SimpleNamespace

from opinion_trading.core.gateway_health import (
    check_gateway_health,
    load_proxy_pool,
    probe_http,
    probe_ws,
    run_cli,
)


class _FakeResp:
    def __init__(self, payload, *, ok=True, status_code=200):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.content = b"{}" if payload is not None else b""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _FakeTransport:
    def __init__(self, *, ready, sentiment):
        self.ready = ready
        self.sentiment = sentiment
        self.gets = []
        self.posts = []

    def get(self, url, timeout=None):
        self.gets.append((url, timeout))
        return self.ready

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append((url, json, headers, timeout))
        return self.sentiment


def test_stub_pass_when_no_url(monkeypatch):
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.delenv("INFERENCE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_GATEWAY_URL", raising=False)
    monkeypatch.delenv("GATEWAY_HEALTH_STUB", raising=False)
    result = check_gateway_health(base_url=None, config_path="no-such.yaml")
    assert result.ok is True
    assert result.mode == "stub"
    assert "HEALTH PASS" in result.log_line()


def test_stub_flag_skips_live_url():
    result = check_gateway_health(
        base_url="http://127.0.0.1:9", stub=True, config_path="no-such.yaml"
    )
    assert result.ok is True
    assert result.mode == "stub"


def test_live_http_pass_with_mocked_transport():
    transport = _FakeTransport(
        ready=_FakeResp({"status": "ok"}),
        sentiment=_FakeResp({"scores": [0.2], "source": "keyword"}),
    )
    result = check_gateway_health(
        base_url="http://gw.test",
        timeout=1.0,
        config_path="no-such.yaml",
        http_transport=transport,
    )
    assert result.ok is True
    assert result.mode == "live"
    assert result.http_sentiment is True
    assert result.http_ready is True
    assert transport.posts[0][0].endswith("/api/v1/sentiment")


def test_live_http_fail_with_mocked_transport():
    transport = _FakeTransport(
        ready=_FakeResp({}, ok=False, status_code=503),
        sentiment=_FakeResp({"scores": []}),
    )
    result = check_gateway_health(
        base_url="http://gw.test",
        timeout=1.0,
        config_path="no-such.yaml",
        http_transport=transport,
    )
    assert result.ok is False
    assert "HEALTH FAIL" in result.log_line()


def test_ws_opener_injected():
    called = {}

    def opener(url, timeout=2.0):
        called["url"] = url
        called["timeout"] = timeout

    info = probe_ws("ws://127.0.0.1:18789", opener=opener)
    assert info["ok"] is True
    assert called["url"].startswith("ws://")


def test_ws_opener_failure():
    def opener(url, timeout=2.0):
        raise ConnectionError("refused")

    info = probe_ws("ws://127.0.0.1:9", opener=opener)
    assert info["ok"] is False


def test_probe_http_uses_transport():
    transport = _FakeTransport(
        ready=_FakeResp({"ready": True}),
        sentiment=_FakeResp({"scores": [0.0]}),
    )
    out = probe_http("http://example", transport=transport, timeout=1)
    assert out["sentiment"]["ok"] is True
    assert out["ready"]["ok"] is True


def test_proxy_pool_from_env_and_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("PROXY_POOL", "http://127.0.0.1:8001, http://127.0.0.1:8002")
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        "collection:\n  proxy_urls:\n    - http://127.0.0.1:8002\n    - socks5://127.0.0.1:1080\n",
        encoding="utf-8",
    )
    urls = load_proxy_pool(str(cfg))
    assert urls == [
        "http://127.0.0.1:8001",
        "http://127.0.0.1:8002",
        "socks5://127.0.0.1:1080",
    ]


def test_cli_stub_exit_zero(monkeypatch, capsys):
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.delenv("INFERENCE_URL", raising=False)
    monkeypatch.delenv("OPENCLAW_GATEWAY_URL", raising=False)
    code = run_cli(["--stub", "--json", "--config", "no-such.yaml"])
    assert code == 0
    out = capsys.readouterr().out
    assert '"mode": "stub"' in out


def test_live_includes_ws_when_injected():
    transport = _FakeTransport(
        ready=_FakeResp({"status": "ok"}),
        sentiment=_FakeResp({"scores": [0.1]}),
    )

    def opener(url, timeout=2.0):
        return SimpleNamespace(ok=True)

    result = check_gateway_health(
        base_url="http://gw.test",
        ws_url="ws://gw.test/ws",
        http_transport=transport,
        ws_opener=opener,
        config_path="no-such.yaml",
    )
    assert result.ok is True
    assert result.ws_ok is True
