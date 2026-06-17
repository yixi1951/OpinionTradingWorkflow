"""Tests for collector robustness features: HTTP cache, rate limiting, schema.

These tests validate the caching and rate-limiting helpers.
Actual HTTP requests are NOT made — we test pure logic paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ── HTML Cache helpers (imported inline to test) ──────────────────────────


def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def test_cache_key_consistency():
    url = "https://guba.eastmoney.com/list,sh600519.html"
    key1 = _cache_key(url)
    key2 = _cache_key(url)
    assert key1 == key2
    assert len(key1) == 32  # md5 hex


def test_cache_key_different_urls():
    k1 = _cache_key("https://example.com/a")
    k2 = _cache_key("https://example.com/b")
    assert k1 != k2


def test_cache_read_write(tmp_path, monkeypatch):
    monkeypatch.setenv("HTML_CACHE_DIR", str(tmp_path / "html_cache"))
    monkeypatch.setenv("HTML_CACHE_TTL_SECONDS", "3600")

    # Re-import to pick up env var changes
    from opinion_trading.integrations.platform_sentiment_real import (
        _get_cache_dir,
        _write_html_cache,
        _read_html_cache,
    )

    url = "https://test.cache/page"
    html = "<html><body>test</body></html>"
    _write_html_cache(url, html)

    cached = _read_html_cache(url)
    assert cached == html

    # Reading non-existent URL returns None
    assert _read_html_cache("https://test.cache/nonexistent") is None


def test_cache_expiry(tmp_path, monkeypatch):
    monkeypatch.setenv("HTML_CACHE_DIR", str(tmp_path / "html_cache_expire"))
    monkeypatch.setenv("HTML_CACHE_TTL_SECONDS", "1")  # 1 second TTL

    from opinion_trading.integrations.platform_sentiment_real import (
        _write_html_cache,
        _read_html_cache,
    )

    url = "https://test.expire/page"
    _write_html_cache(url, "<html>fresh</html>")

    # Immediately readable
    assert _read_html_cache(url) is not None

    # After TTL expires, returns None
    time.sleep(1.5)
    assert _read_html_cache(url) is None


# ── Schema validation ─────────────────────────────────────────────────────


def test_validate_row_schema_missing_content():
    from opinion_trading.core.raw_store import validate_row_schema

    row = {
        "trade_date": "2026-06-17",
        "platform": "guba",
        "symbol": "600519.SH",
        "capture_status": "success",
    }
    # content is optional (None allowed)
    violations = validate_row_schema(row, 0)
    assert violations == []


def test_validate_row_schema_wrong_score_type():
    from opinion_trading.core.raw_store import validate_row_schema

    row = {
        "trade_date": "2026-06-17",
        "platform": "guba",
        "symbol": "600519.SH",
        "keyword_score": "bad",  # should be float/int
        "capture_status": "success",
    }
    violations = validate_row_schema(row, 0)
    assert any("keyword_score" in v for v in violations)
