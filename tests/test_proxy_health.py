from __future__ import annotations

from opinion_trading.core.proxy_health import (
    ProxyProbeResult,
    check_proxy_health,
    probe_one_proxy,
    redact_proxy_url,
    run_cli,
)


class _FakeResp:
    def __init__(self, *, ok=True, status_code=200):
        self.ok = ok
        self.status_code = status_code


class _FakeTransport:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def get(self, url, proxies=None, timeout=None):
        self.calls.append((url, proxies, timeout))
        proxy = (proxies or {}).get("http") or (proxies or {}).get("https")
        spec = self.mapping.get(proxy)
        if spec is None:
            raise ConnectionError(f"unmapped proxy {proxy}")
        if isinstance(spec, Exception):
            raise spec
        return spec


def test_redact_proxy_url_strips_userinfo():
    assert redact_proxy_url("http://user:secret@127.0.0.1:8888") == "http://***@127.0.0.1:8888"
    assert redact_proxy_url("http://127.0.0.1:8888") == "http://127.0.0.1:8888"


def test_empty_pool_skip_pass(monkeypatch):
    monkeypatch.delenv("PROXY_POOL", raising=False)
    report = check_proxy_health(config_path="no-such.yaml")
    assert report.ok is True
    assert report.skipped is True
    assert report.configured == 0
    assert "PROXY HEALTH PASS" in report.log_line()
    assert "skip" in report.message.lower() or "CI-safe" in report.message


def test_empty_cli_exit_zero(monkeypatch, capsys):
    monkeypatch.delenv("PROXY_POOL", raising=False)
    code = run_cli(["--config", "no-such.yaml", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    assert '"skipped": true' in out


def test_mixed_pool_pass_with_mocked_transport(monkeypatch):
    monkeypatch.setenv("PROXY_POOL", "http://good:1,http://bad:2")
    transport = _FakeTransport(
        {
            "http://good:1": _FakeResp(ok=True, status_code=200),
            "http://bad:2": ConnectionError("refused"),
        }
    )
    report = check_proxy_health(
        config_path="no-such.yaml", timeout=1.0, transport=transport, probe_url="http://example.com/"
    )
    assert report.ok is True
    assert report.skipped is False
    assert report.passed == 1
    assert report.failed == 1
    assert report.configured == 2
    table = "\n".join(report.table_lines())
    assert "PASS" in table
    assert "FAIL" in table
    assert len(transport.calls) == 2


def test_all_proxies_fail_exit_nonzero(monkeypatch):
    monkeypatch.setenv("PROXY_POOL", "http://dead:1")
    transport = _FakeTransport({"http://dead:1": TimeoutError("slow")})
    report = check_proxy_health(
        config_path="no-such.yaml", timeout=0.5, transport=transport
    )
    assert report.ok is False
    assert "PROXY HEALTH FAIL" in report.log_line()


def test_cli_all_fail_exit_one(monkeypatch):
    monkeypatch.setenv("PROXY_POOL", "http://dead:1")
    monkeypatch.setattr(
        "opinion_trading.core.proxy_health.probe_one_proxy",
        lambda *a, **k: ProxyProbeResult(
            url="http://dead:1",
            display_url="http://dead:1",
            ok=False,
            error="nope",
        ),
    )
    code = run_cli(["--config", "no-such.yaml", "--json"])
    assert code == 1


def test_probe_one_uses_transport():
    transport = _FakeTransport({"http://p:9": _FakeResp(status_code=204, ok=True)})
    row = probe_one_proxy(
        "http://p:9", probe_url="http://example.com/", timeout=1, transport=transport
    )
    assert row.ok is True
    assert row.status_code == 204
    assert transport.calls[0][1]["https"] == "http://p:9"


def test_yaml_pool_and_extra(tmp_path, monkeypatch):
    monkeypatch.delenv("PROXY_POOL", raising=False)
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        "collection:\n  proxy_urls:\n    - http://yaml:1\n",
        encoding="utf-8",
    )
    transport = _FakeTransport(
        {
            "http://yaml:1": _FakeResp(status_code=200),
            "http://extra:2": _FakeResp(status_code=200),
        }
    )
    report = check_proxy_health(
        config_path=str(cfg), extra=["http://extra:2"], transport=transport
    )
    assert report.configured == 2
    assert report.passed == 2


def test_http_error_status_is_fail():
    transport = _FakeTransport({"http://p:1": _FakeResp(ok=False, status_code=502)})
    row = probe_one_proxy("http://p:1", transport=transport)
    assert row.ok is False
    assert row.status_code == 502


def test_main_accepts_proxy_health_mode(monkeypatch):
    import sys

    from opinion_trading import main as main_module

    monkeypatch.setattr(sys, "argv", ["prog", "--mode", "proxy-health"])
    assert main_module.parse_args().mode == "proxy-health"


def test_main_proxy_health_empty_pool_ok(monkeypatch, capsys):
    import sys

    from opinion_trading import main as main_module

    monkeypatch.delenv("PROXY_POOL", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--mode", "proxy-health", "--config", "no-such.yaml"],
    )
    main_module.main()
    out = capsys.readouterr().out
    assert "PROXY HEALTH PASS" in out
