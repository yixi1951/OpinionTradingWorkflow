"""More targeted coverage tests for remaining gaps."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── Platform Sentiment Stub ───────────────────────────────────────────────


def test_stub_provider_fetch():
    """Stub provider returns expected structure."""
    from opinion_trading.integrations.platform_sentiment_stub import (
        PlatformSentimentProvider,
    )

    provider = PlatformSentimentProvider()
    result = provider.fetch("guba", "600519.SH", date(2026, 6, 17))

    assert "sentiment_score" in result
    assert "post_count" in result
    assert "source" in result
    assert -1.0 <= result["sentiment_score"] <= 1.0
    assert result["post_count"] >= 50
    assert result["source"] == "stub://guba"


def test_stub_provider_deterministic():
    """Same inputs produce same outputs (seeded Random)."""
    from opinion_trading.integrations.platform_sentiment_stub import (
        PlatformSentimentProvider,
    )

    provider = PlatformSentimentProvider()
    r1 = provider.fetch("xueqiu", "000001.SZ", date(2026, 6, 17))
    r2 = provider.fetch("xueqiu", "000001.SZ", date(2026, 6, 17))
    assert r1["sentiment_score"] == r2["sentiment_score"]
    assert r1["post_count"] == r2["post_count"]


def test_stub_provider_different_platforms():
    """Different platforms produce different results."""
    from opinion_trading.integrations.platform_sentiment_stub import (
        PlatformSentimentProvider,
    )

    provider = PlatformSentimentProvider()
    r1 = provider.fetch("guba", "600519.SH", date(2026, 6, 17))
    r2 = provider.fetch("eastmoney", "600519.SH", date(2026, 6, 17))
    # Different platform seed = different result
    assert r1["sentiment_score"] != r2["sentiment_score"]


# ── Memory Store ───────────────────────────────────────────────────────────


def test_memory_store_append_many(tmp_path):
    """append_many writes JSONL records."""
    from opinion_trading.core.memory_store import JsonLineMemoryStore

    store = JsonLineMemoryStore(str(tmp_path))
    store.append_many("test.jsonl", [{"a": 1}, {"b": 2}])

    lines = (tmp_path / "test.jsonl").read_text("utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"a": 1}
    assert json.loads(lines[1]) == {"b": 2}


def test_memory_store_save_and_load_state(tmp_path):
    """save_state writes JSON, load_state reads it back."""
    from opinion_trading.core.memory_store import JsonLineMemoryStore

    store = JsonLineMemoryStore(str(tmp_path))
    store.save_state({"key": "value", "num": 42})
    loaded = store.load_state()
    assert loaded == {"key": "value", "num": 42}


def test_memory_store_read_all_with_data(tmp_path):
    """read_all returns all records from file."""
    from opinion_trading.core.memory_store import JsonLineMemoryStore

    store = JsonLineMemoryStore(str(tmp_path))
    store.append_many("data.jsonl", [{"x": 1}, {"x": 2}, {"x": 3}])
    records = store.read_all("data.jsonl")
    assert len(records) == 3
    assert records[-1]["x"] == 3


# ── Backtest ───────────────────────────────────────────────────────────────


def test_backtest_save_results(tmp_path):
    """save_results writes CSV with header."""
    from opinion_trading.core.backtest import StrategyBacktester, BacktestResult

    results = [
        BacktestResult(
            bearish_threshold=-0.1,
            bullish_threshold=0.1,
            platforms=["guba", "eastmoney"],
            annual_return=0.15,
            max_drawdown=-0.05,
            sharpe=1.2,
            final_equity=11500.0,
        ),
    ]
    file_path = str(tmp_path / "results.csv")
    engine = MagicMock(spec=StrategyBacktester)
    StrategyBacktester.save_results(engine, results, file_path)

    content = Path(file_path).read_text("utf-8")
    assert "bearish_threshold" in content
    assert "0.15" in content


# ── Raw Store ──────────────────────────────────────────────────────────────


def test_raw_store_save_failure_logs(tmp_path, monkeypatch):
    """save_failure_logs writes JSONL for failed captures."""
    monkeypatch.setattr(
        "opinion_trading.core.raw_store.RawPostCsvStore._normalize_row",
        lambda self, r: r,
    )

    from opinion_trading.core.raw_store import RawPostCsvStore

    store = RawPostCsvStore(str(tmp_path))
    rows = [
        {
            "trade_date": "2026-06-17",
            "platform": "guba",
            "symbol": "600519.SH",
            "capture_status": "timeout",
            "failure_reason": "Connection reset",
        },
        {
            "trade_date": "2026-06-17",
            "platform": "eastmoney",
            "symbol": "600519.SH",
            "capture_status": "success",
        },
    ]
    paths = store.save_failure_logs("2026-06-17", rows)

    assert "combined" in paths
    combined_path = paths["combined"]
    assert combined_path.exists()
    content = combined_path.read_text("utf-8")
    # Only the timeout row should be in failure logs
    assert "Connection reset" in content
    assert "success" not in content


# ── Config Loader ──────────────────────────────────────────────────────────


def test_config_loader_load_runtime_config(tmp_path):
    """load_runtime_config reads platform list correctly."""
    import yaml
    from opinion_trading.core.config_loader import load_runtime_config

    config_yaml = """
universe:
  symbols:
    - 600519.SH
strategy:
  platforms:
    - guba
    - eastmoney
  platform_weights:
    guba: 1.0
    eastmoney: 1.0
  bullish_threshold: 0.1
  bearish_threshold: -0.1
  min_platforms_for_signal: 2
  reversal_min_delta: 0.1
  initial_cash: 100000
  position_size_ratio: 0.2
storage:
  raw_dir: data/raw
  memory_dir: data/memory
  report_dir: data/reports
"""
    with open(tmp_path / "settings.yaml", "w") as f:
        f.write(config_yaml)

    config = load_runtime_config(str(tmp_path / "settings.yaml"))
    assert len(config.strategy.platforms) == 2
    assert "guba" in config.strategy.platforms
