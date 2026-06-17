"""Targeted tests to boost coverage on high-impact modules.

These focus on pure logic paths that don't require real APIs.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Config Loader ──────────────────────────────────────────────────────────


def test_config_loader_yaml_missing(monkeypatch):
    """_load_yaml raises when yaml is None (not installed)."""
    monkeypatch.setattr(
        "opinion_trading.core.config_loader.yaml", None
    )
    from opinion_trading.core.config_loader import _load_yaml

    with pytest.raises(ModuleNotFoundError, match="PyYAML is required"):
        _load_yaml(Path("dummy.yaml"))


# ── Memory Store ───────────────────────────────────────────────────────────


def test_memory_store_read_all_missing(tmp_path):
    """read_all returns [] when file doesn't exist."""
    from opinion_trading.core.memory_store import JsonLineMemoryStore

    store = JsonLineMemoryStore(str(tmp_path))
    result = store.read_all("nonexistent.jsonl")
    assert result == []


def test_memory_store_load_state_missing(tmp_path):
    """load_state returns {} when file doesn't exist."""
    from opinion_trading.core.memory_store import JsonLineMemoryStore

    store = JsonLineMemoryStore(str(tmp_path))
    result = store.load_state("nonexistent.json")
    assert result == {}


# ── Metrics ────────────────────────────────────────────────────────────────


def test_metrics_empty_curve():
    """Empty equity curve returns all zeros."""
    from opinion_trading.core.metrics import compute_performance_metrics

    result = compute_performance_metrics([])
    assert result["annual_return"] == 0.0
    assert result["max_drawdown"] == 0.0
    assert result["sharpe"] == 0.0
    assert result["final_equity"] == 0.0


def test_metrics_single_element():
    """Single-element equity curve returns zero metrics."""
    from opinion_trading.core.metrics import compute_performance_metrics

    result = compute_performance_metrics([100.0])
    assert result["final_equity"] == 100.0
    assert result["annual_return"] == 0.0


def test_metrics_start_zero():
    """Start value of zero returns zero annual return."""
    from opinion_trading.core.metrics import compute_performance_metrics

    result = compute_performance_metrics([0.0, 100.0, 200.0])
    assert result["annual_return"] == 0.0
    assert result["final_equity"] == 200.0


def test_metrics_negative_prev_return():
    """Previous value <= 0 results in 0.0 return."""
    from opinion_trading.core.metrics import compute_performance_metrics

    result = compute_performance_metrics([100.0, 0.0, 50.0])
    # second step: prev=0, so return is 0.0
    assert result["final_equity"] == 50.0


# ── AI Sentiment — OpenClaw Fallback ──────────────────────────────────────


def test_ai_sentiment_openclaw_not_configured(monkeypatch):
    """When OpenClaw is not configured, falls through to keyword."""
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")

    from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

    analyzer = AISentimentAnalyzer()
    # Ensure openclaw is None (not configured)
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["市场今日震荡走高，收红盘"])
    assert len(results) == 1
    assert results[0].source == "keyword"


def test_ai_sentiment_openclaw_fallback_on_wrong_count(monkeypatch):
    """If OpenClaw returns wrong number of scores, fallback to keyword."""
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")

    from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.score_texts.return_value = [0.5]  # only 1 score for 2 texts

    analyzer = AISentimentAnalyzer()
    analyzer.openclaw = mock_client
    analyzer._pipeline = None

    results = analyzer.analyze_texts(["text one", "text two"])
    # Should fallback to keyword since count mismatch
    assert len(results) == 2
    assert results[0].source == "keyword"


def test_ai_sentiment_openclaw_fallback_on_exception(monkeypatch):
    """If OpenClaw raises, fallback to keyword."""
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")

    from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.score_texts.side_effect = RuntimeError("Connection refused")

    analyzer = AISentimentAnalyzer()
    analyzer.openclaw = mock_client
    analyzer._pipeline = None

    results = analyzer.analyze_texts(["test text"])
    assert len(results) == 1
    assert results[0].source == "keyword"


def test_ai_sentiment_openclaw_success():
    """OpenClaw returns valid scores."""
    from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.score_texts.return_value = [0.5, -0.3, 0.0]

    analyzer = AISentimentAnalyzer()
    analyzer.openclaw = mock_client
    analyzer._pipeline = None

    results = analyzer.analyze_texts(["good news", "bad news", "neutral"])
    assert len(results) == 3
    assert results[0].source == "openclaw"
    assert results[0].score == 0.5
    assert results[1].score == -0.3
    assert results[2].score == 0.0


def test_ai_sentiment_openclaw_clamp_score():
    """Score clamping keeps values within [-1, 1]."""
    from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.score_texts.return_value = [2.5, -3.0, 0.0]

    analyzer = AISentimentAnalyzer()
    analyzer.openclaw = mock_client
    analyzer._pipeline = None

    results = analyzer.analyze_texts(["huge", "small", "mid"])
    assert results[0].score == 1.0
    assert results[1].score == -1.0
    assert results[2].score == 0.0


# ── Log Utils — rotate with log_dir ────────────────────────────────────────


def test_configure_logging_with_log_dir(tmp_path, monkeypatch):
    """configure_logging with log_dir creates file at default name."""
    from opinion_trading.core.log_utils import configure_logging, get_logger, reset_logging

    reset_logging()

    log_dir = str(tmp_path / "logs")
    configure_logging(level="DEBUG", log_dir=log_dir)

    logger = get_logger("test_log_dir")
    logger.info("test message for log_dir")

    for handler in logging.getLogger().handlers[:]:
        handler.flush()
        handler.close()

    # Default log file name
    log_file = tmp_path / "logs" / "opinion_trading.log"
    assert log_file.exists()
    content = log_file.read_text("utf-8")
    assert "test message for log_dir" in content


# ── Schema validation completeness ─────────────────────────────────────────


def test_schema_validation_missing_required_field():
    """Missing required field 'trade_date' is flagged."""
    from opinion_trading.core.raw_store import validate_row_schema

    row = {
        "platform": "guba",
        "symbol": "600519.SH",
        "capture_status": "success",
    }
    violations = validate_row_schema(row, 0)
    assert any("missing required" in v for v in violations)


def test_schema_validation_empty_required_field():
    """Empty string required field is flagged."""
    from opinion_trading.core.raw_store import validate_row_schema

    row = {
        "trade_date": "",
        "platform": "guba",
        "symbol": "600519.SH",
        "capture_status": "success",
    }
    violations = validate_row_schema(row, 1)
    assert any("missing required" in v for v in violations)


def test_schema_validation_wrong_type():
    """Non-string symbol should be flagged."""
    from opinion_trading.core.raw_store import validate_row_schema

    row = {
        "trade_date": "2026-06-17",
        "platform": "guba",
        "symbol": 123,  # wrong type
        "capture_status": "success",
    }
    violations = validate_row_schema(row, 2)
    assert any("symbol" in v for v in violations)


# ── OpenClaw Adapter edge cases ──────────────────────────────────────────


def test_openclaw_adapter_probe_exception():
    """probe() returns error dict when connection fails."""
    from opinion_trading.core.openclaw_adapter import OpenClawClient

    client = OpenClawClient(base_url="http://localhost:1", token="x", timeout=1)
    result = client.probe()
    assert result["connected"] is False


def test_openclaw_adapter_timeout_config():
    """Custom timeout via env var OPENCLAW_TIMEOUT."""
    import os
    os.environ["OPENCLAW_TIMEOUT"] = "30"
    from opinion_trading.core.openclaw_adapter import OpenClawClient

    client = OpenClawClient(base_url="http://test.test", token="x")
    assert client.timeout == 30
    del os.environ["OPENCLAW_TIMEOUT"]


def test_openclaw_adapter_probe_success():
    """probe() returns connected=True when gateway responds."""
    from opinion_trading.core.openclaw_adapter import OpenClawClient

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"scores": [0.25]}
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp):
        client = OpenClawClient(base_url="http://fake.test", token="x", timeout=5)
        result = client.probe()
        assert result["connected"] is True
        assert result["sample_score"] == 0.25


# ── Models ────────────────────────────────────────────────────────────────


def test_models_strategy_config_defaults():
    """StrategyConfig with no weights uses defaults."""
    from opinion_trading.core.models import StrategyConfig

    config = StrategyConfig(
        platforms=["guba"],
        platform_weights={},
        bearish_threshold=-0.5,
        bullish_threshold=0.5,
        min_platforms_for_signal=2,
        reversal_min_delta=0.1,
        initial_cash=100000.0,
        position_size_ratio=0.2,
    )
    assert config.platform_weights == {}
    assert config.bearish_threshold == -0.5


def test_models_runtime_config():
    """RuntimeConfig stores all fields."""
    from opinion_trading.core.models import RuntimeConfig, StrategyConfig

    sc = StrategyConfig(
        platforms=["guba", "eastmoney"],
        platform_weights={"guba": 1.0},
        bearish_threshold=-0.1,
        bullish_threshold=0.1,
        min_platforms_for_signal=2,
        reversal_min_delta=0.1,
        initial_cash=100000.0,
        position_size_ratio=0.2,
    )
    rc = RuntimeConfig(
        strategy=sc,
        symbols=["600519.SH"],
        memory_dir="data/memory",
        report_dir="data/reports",
        raw_dir="data/raw",
    )
    assert len(rc.symbols) == 1
    assert rc.strategy.platforms == ["guba", "eastmoney"]


# ── AI Sentiment — to_dict and labels ─────────────────────────────────────


def test_ai_sentiment_result_to_dict():
    """SentimentResult.to_dict returns correct dict."""
    from opinion_trading.core.ai_sentiment import SentimentResult

    r = SentimentResult(
        score=0.5,
        source="openclaw",
        confidence=0.8,
        pos_hits=3,
        neg_hits=1,
    )
    d = r.to_dict()
    assert d["score"] == 0.5
    assert d["source"] == "openclaw"
    assert d["pos_hits"] == 3
    assert d["neg_hits"] == 1


def test_ai_sentiment_english_label():
    """sentiment_intensity_label works for English."""
    from opinion_trading.core.ai_sentiment import sentiment_intensity_label

    assert sentiment_intensity_label(0.4, "en") == "Strong bullish"
    assert sentiment_intensity_label(0.2, "en") == "Bullish"
    assert sentiment_intensity_label(-0.4, "en") == "Strong bearish"
    assert sentiment_intensity_label(-0.2, "en") == "Bearish"
    assert sentiment_intensity_label(0.0, "en") == "Neutral"
