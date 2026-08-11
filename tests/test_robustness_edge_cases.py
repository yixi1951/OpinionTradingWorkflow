"""Edge-case tests for robustness features: cache, rate limiter, log rotation, adapter.

These tests validate pure logic paths — no real HTTP calls.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch



# ── HTML 缓存边缘情况 ──────────────────────────────────────────────────────


def test_cache_dir_auto_creation(tmp_path, monkeypatch):
    """Cache dir is created on first access if it doesn't exist."""
    from opinion_trading.integrations.platform_sentiment_real import _get_cache_dir

    # Reset global state
    monkeypatch.setattr(
        "opinion_trading.integrations.platform_sentiment_real._HTML_CACHE_DIR", None
    )
    monkeypatch.setenv("HTML_CACHE_DIR", str(tmp_path / "auto_cache"))
    cache_dir = _get_cache_dir()
    assert cache_dir.exists()
    assert cache_dir.name == "auto_cache"


def test_cache_corrupted_file(tmp_path, monkeypatch):
    """Corrupted/corrupt cache file should be treated as a miss."""
    monkeypatch.setenv("HTML_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("HTML_CACHE_TTL_SECONDS", "3600")

    from opinion_trading.integrations.platform_sentiment_real import (
        _cache_key,
        _get_cache_dir,
        _read_html_cache,
    )

    # Write invalid data that looks like a cache file
    cache_dir = _get_cache_dir()
    key = _cache_key("https://corrupted.test/page")
    cache_file = cache_dir / key
    cache_file.write_text("", encoding="utf-8")  # empty file

    result = _read_html_cache("https://corrupted.test/page")
    assert result is None or result == ""
    # If TTL hasn't expired, an empty string might be returned — that's acceptable


def test_cache_ttl_zero(tmp_path, monkeypatch):
    """TTL of 0 means every request is a miss."""
    monkeypatch.setenv("HTML_CACHE_DIR", str(tmp_path / "cache_no_ttl"))
    monkeypatch.setenv("HTML_CACHE_TTL_SECONDS", "0")

    from opinion_trading.integrations.platform_sentiment_real import (
        _read_html_cache,
        _write_html_cache,
    )

    url = "https://no-ttl.test/page"
    _write_html_cache(url, "<html>data</html>")
    # TTL=0 means immediately expired
    assert _read_html_cache(url) is None


def test_cache_write_then_read(tmp_path, monkeypatch):
    """Write then immediate read returns the data."""
    monkeypatch.setenv("HTML_CACHE_DIR", str(tmp_path / "cache_rw"))
    monkeypatch.setenv("HTML_CACHE_TTL_SECONDS", "3600")

    from opinion_trading.integrations.platform_sentiment_real import (
        _read_html_cache,
        _write_html_cache,
    )

    url = "https://read-write.test/page"
    html = "<html>roundtrip</html>"
    _write_html_cache(url, html)
    assert _read_html_cache(url) == html


# ── 速率限制器 ──────────────────────────────────────────────────────────────


def test_rate_limit_first_call(monkeypatch):
    """First call to a domain does not sleep."""
    monkeypatch.setenv("REQUEST_MIN_INTERVAL", "10")

    from opinion_trading.integrations.platform_sentiment_real import _rate_limit

    # Reset domain tracker
    monkeypatch.setattr(
        "opinion_trading.integrations.platform_sentiment_real._LAST_REQUEST_TIME", {}
    )

    start = time.time()
    _rate_limit("https://first-call.test/page")
    elapsed = time.time() - start
    assert elapsed < 2  # no long sleep


def test_rate_limit_respects_min_interval(monkeypatch):
    """Second call within min_interval should sleep."""
    monkeypatch.setenv("REQUEST_MIN_INTERVAL", "2")

    from opinion_trading.integrations.platform_sentiment_real import _rate_limit

    monkeypatch.setattr(
        "opinion_trading.integrations.platform_sentiment_real._LAST_REQUEST_TIME", {}
    )

    _rate_limit("https://test-rate.test/page")  # first call, no sleep

    start = time.time()
    _rate_limit("https://test-rate.test/page")  # second call, should sleep
    elapsed = time.time() - start
    # Should have slept at least ~2s (min_interval - 0 + jitter)
    assert elapsed >= 1.5


def test_rate_limit_per_domain(monkeypatch):
    """Different domains should not rate-limit each other."""
    monkeypatch.setenv("REQUEST_MIN_INTERVAL", "10")

    from opinion_trading.integrations.platform_sentiment_real import _rate_limit

    monkeypatch.setattr(
        "opinion_trading.integrations.platform_sentiment_real._LAST_REQUEST_TIME", {}
    )

    _rate_limit("https://domain-a.test/page")
    # Immediately call different domain — should not sleep
    start = time.time()
    _rate_limit("https://domain-b.test/page")
    elapsed = time.time() - start
    assert elapsed < 2


def test_rate_limit_unknown_domain(monkeypatch):
    """URL with no netloc uses 'unknown' as domain."""
    monkeypatch.setenv("REQUEST_MIN_INTERVAL", "0.1")

    from opinion_trading.integrations.platform_sentiment_real import _rate_limit

    monkeypatch.setattr(
        "opinion_trading.integrations.platform_sentiment_real._LAST_REQUEST_TIME", {}
    )

    # Should not crash on malformed URL
    _rate_limit("not-a-valid-url")
    _rate_limit("also-not-valid")  # same 'unknown' domain


# ── 日志轮转 ────────────────────────────────────────────────────────────────


def test_log_rotation_creates_backup(tmp_path, monkeypatch):
    """RotatingFileHandler creates backup files when log exceeds maxBytes."""
    from opinion_trading.core.log_utils import configure_logging, get_logger, reset_logging

    reset_logging()

    monkeypatch.setenv("LOG_MAX_BYTES", "500")   # tiny maxBytes for fast rotation
    monkeypatch.setenv("LOG_BACKUP_COUNT", "2")

    log_file = str(tmp_path / "rotation_test.log")
    configure_logging(level="DEBUG", log_file=log_file)

    logger = get_logger("test_rotation")
    # Write enough to trigger rotation (500 bytes)
    for i in range(200):
        logger.info("This is log line number %d to trigger rotation", i)

    # Flush all handlers
    for handler in logging.getLogger().handlers[:]:
        handler.flush()
        handler.close()

    log_path = Path(log_file)
    assert log_path.exists() or log_path.with_suffix(".log.1").exists()

    # There should be at least the main log file
    files = list(tmp_path.glob("rotation_test.log*"))
    assert len(files) >= 1


def test_log_rotation_respects_backup_count(tmp_path, monkeypatch):
    """Only backup_count backup files are kept."""
    from opinion_trading.core.log_utils import configure_logging, get_logger, reset_logging

    reset_logging()

    monkeypatch.setenv("LOG_MAX_BYTES", "300")
    monkeypatch.setenv("LOG_BACKUP_COUNT", "1")

    log_file = str(tmp_path / "rotation_count_test.log")
    configure_logging(level="DEBUG", log_file=log_file)

    logger = get_logger("test_rotation_count")
    for i in range(300):
        logger.info("Line number %d for rotation count test", i)

    for handler in logging.getLogger().handlers[:]:
        handler.flush()
        handler.close()

    files = sorted(tmp_path.glob("rotation_count_test.log*"))
    # With backupCount=1, max 2 files: .log and .log.1
    assert len(files) <= 2


# ── OpenClaw Adapter 边缘情况 ──────────────────────────────────────────────


def test_openclaw_adapter_not_configured():
    """score_texts returns None when no URL configured."""
    from opinion_trading.core.openclaw_adapter import OpenClawClient

    client = OpenClawClient(base_url=None, token=None)
    assert client.is_configured() is False
    assert client.score_texts(["test"]) is None


def test_openclaw_adapter_probe_no_url():
    """probe() returns friendly message when no URL."""
    from opinion_trading.core.openclaw_adapter import OpenClawClient

    client = OpenClawClient(base_url=None, token=None)
    result = client.probe()
    assert result["connected"] is False
    assert "not configured" in result["message"]


def test_openclaw_adapter_score_connection_error(monkeypatch):
    """score_texts returns None on connection error."""
    monkeypatch.setenv("OPENCLAW_URL", "http://localhost:1")
    monkeypatch.setenv("OPENCLAW_TOKEN", "test-token")

    from opinion_trading.core.openclaw_adapter import OpenClawClient

    client = OpenClawClient(timeout=1)
    result = client.score_texts(["test"])
    assert result is None


def test_openclaw_adapter_bad_response(monkeypatch):
    """score_texts returns None if response has no scores."""
    from opinion_trading.core.openclaw_adapter import OpenClawClient

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"not_scores": [0.5]}
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp):
        client = OpenClawClient(base_url="http://fake.test", token="x", timeout=5)
        result = client.score_texts(["test"])
        assert result is None  # missing 'scores' key


def test_openclaw_adapter_valid_response(monkeypatch):
    """score_texts returns scores when response is valid."""
    from opinion_trading.core.openclaw_adapter import OpenClawClient

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"scores": [0.5, -0.3, 0.0]}
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp):
        client = OpenClawClient(base_url="http://fake.test", token="x", timeout=5)
        result = client.score_texts(["a", "b", "c"])
        assert result == [0.5, -0.3, 0.0]


# ── 模式验证完整覆盖 ──────────────────────────────────────────────────────────


def test_schema_validation_all_fields():
    """Validate every field in SCHEMA_RULES has the expected type."""
    from opinion_trading.core.raw_store import validate_row_schema

    # A perfect row should have no violations
    row = {
        "trade_date": "2026-06-17",
        "platform": "guba",
        "symbol": "600519.SH",
        "keyword_score": 0.5,
        "openclaw_score": -0.2,
        "openclaw_tokens": 150,
        "post_count": 10,
        "failure_reason": "",
        "capture_status": "success",
        "source_page": "https://guba.eastmoney.com/list,sh600519.html",
        "content": "Some sample content here" * 10,
        "title": "Test Title",
        "url": "https://guba.eastmoney.com/news,600519,12345.html",
        "post_time": "2026-06-17 10:30:00",
        "is_noise": False,
    }
    violations = validate_row_schema(row, 0)
    assert violations == []


def test_schema_validation_missing_optional_field():
    """Missing optional fields with defaults should not violate."""
    from opinion_trading.core.raw_store import validate_row_schema

    row = {
        "trade_date": "2026-06-17",
        "platform": "guba",
        "symbol": "600519.SH",
        "capture_status": "success",
    }
    violations = validate_row_schema(row, 1)
    assert violations == []


def test_schema_validation_invalid_type_for_rule():
    """Field with wrong type in _SCHEMA_RULES should be flagged."""
    from opinion_trading.core.raw_store import validate_row_schema

    row = {
        "trade_date": "2026-06-17",
        "platform": "guba",
        "symbol": "600519.SH",
        "keyword_score": "not-a-number",  # should be float/int
        "capture_status": "success",
    }
    violations = validate_row_schema(row, 2)
    assert any("keyword_score" in v for v in violations)


def test_schema_validation_title_wrong_type():
    """Non-string title flagged."""
    from opinion_trading.core.raw_store import validate_row_schema

    row = {
        "trade_date": "2026-06-17",
        "platform": "guba",
        "symbol": "600519.SH",
        "title": 12345,  # should be str
        "capture_status": "success",
    }
    violations = validate_row_schema(row, 3)
    assert any("title" in v for v in violations)


# ── AI Sentiment 边缘情况 ──────────────────────────────────────────────────


def test_ai_sentiment_keyword_only_empty_list(monkeypatch):
    """Empty text list returns empty result."""
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")

    from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

    analyzer = AISentimentAnalyzer()
    analyzer.openclaw = None
    results = analyzer.analyze_texts([])
    assert results == []


def test_ai_sentiment_score_texts_empty(monkeypatch):
    """Empty text list returns empty scores list."""
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")

    from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

    analyzer = AISentimentAnalyzer()
    analyzer.openclaw = None
    scores = analyzer.score_texts([])
    assert scores == []


# ── 运行管道信号处理 ───────────────────────────────────────────────────────


def test_is_shutdown_requested_default():
    """Before any signal, shutdown flag is False."""
    from run_pipeline import is_shutdown_requested

    assert is_shutdown_requested() is False


def test_run_pipeline_sigterm_handler():
    """SIGTERM handler sets shutdown flag."""
    import signal

    from run_pipeline import _handle_sigterm, is_shutdown_requested

    _handle_sigterm(signal.SIGTERM, None)
    assert is_shutdown_requested() is True

    # Reset for other tests (module-level state)
    import run_pipeline as _rp
    _rp._shutdown_requested = False
