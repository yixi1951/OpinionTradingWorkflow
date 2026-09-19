from __future__ import annotations

import requests

from opinion_trading.core.proxy_pool import (
    ProxyRotator,
    get_proxy_rotator,
    set_proxy_rotator,
)
from opinion_trading.integrations.platform_sentiment_real import (
    RealPlatformSentimentProvider,
)


def test_round_robin_skips_failed_then_resets() -> None:
    rotator = ProxyRotator(["http://p1:1", "http://p2:2", "http://p3:3"])
    assert rotator.next() == "http://p1:1"
    assert rotator.next() == "http://p2:2"
    rotator.mark_failure("http://p3:3")
    assert rotator.next() == "http://p1:1"
    assert rotator.next() == "http://p2:2"
    # p3 still failed → skip, wrap, then pool exhausted so failed set clears
    rotator.mark_failure("http://p1:1")
    rotator.mark_failure("http://p2:2")
    recovered = rotator.next()
    assert recovered in {"http://p1:1", "http://p2:2", "http://p3:3"}
    rotator.mark_success(recovered)
    rotator.reset()
    assert rotator.failed_count == 0
    assert rotator.next() == "http://p1:1"


def test_empty_pool_returns_none() -> None:
    rotator = ProxyRotator([])
    assert rotator.next() is None
    assert rotator.requests_proxies() is None


def test_requests_proxies_maps_http_https() -> None:
    rotator = ProxyRotator(["http://127.0.0.1:8888"])
    mapped = rotator.requests_proxies()
    assert mapped == {
        "http": "http://127.0.0.1:8888",
        "https": "http://127.0.0.1:8888",
    }


def test_download_html_round_robin_failover(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HTML_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("HTML_CACHE_DIR", str(tmp_path / "html_cache"))
    monkeypatch.setenv("REQUEST_MIN_INTERVAL", "0")
    rotator = ProxyRotator(["http://p1:1", "http://p2:2"])
    set_proxy_rotator(rotator)
    seen: list[dict | None] = []

    class _Resp:
        status_code = 200
        text = "<html><p>ok-proxy-failover</p></html>"
        apparent_encoding = "utf-8"
        encoding = "utf-8"

        def raise_for_status(self) -> None:
            return None

    def fake_get(url, headers=None, timeout=None, proxies=None):
        seen.append(proxies)
        if proxies and proxies.get("http") == "http://p1:1":
            raise requests.ConnectionError("p1 down")
        return _Resp()

    monkeypatch.setattr(
        "opinion_trading.integrations.platform_sentiment_real.requests.get",
        fake_get,
    )
    try:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        html = provider._download_html("http://example.test/xhs-demo")
        assert "ok-proxy-failover" in html
        assert any(p and p.get("http") == "http://p1:1" for p in seen)
        assert any(p and p.get("http") == "http://p2:2" for p in seen)
        assert rotator.failed_count >= 1
    finally:
        set_proxy_rotator(None)


def test_get_proxy_rotator_reload(monkeypatch) -> None:
    monkeypatch.setenv("PROXY_POOL", "http://env-proxy:9")
    set_proxy_rotator(None)
    rotator = get_proxy_rotator(reload=True)
    assert "http://env-proxy:9" in rotator.urls
    set_proxy_rotator(None)
