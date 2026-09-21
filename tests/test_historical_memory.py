from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from opinion_trading.core.historical_memory import (
    apply_recall_to_signals,
    format_recall_snippet,
    memory_has_history,
    prune_memory_jsonl,
    query_memory,
    recall_symbol_context,
    resolve_recall_enabled,
)
from opinion_trading.core.memory_store import JsonLineMemoryStore
from opinion_trading.core.models import MemoryRecallConfig, TradeSignal


def _seed_memory(tmp_path: Path) -> None:
    store = JsonLineMemoryStore(str(tmp_path))
    today = date.today()
    d0 = (today - timedelta(days=2)).isoformat()
    d1 = (today - timedelta(days=1)).isoformat()
    store.append_many(
        "sentiment_history.jsonl",
        [
            {
                "trade_date": d0,
                "symbol": "600519.SH",
                "platform": "guba",
                "sentiment_score": 0.2,
            },
            {
                "trade_date": d1,
                "symbol": "600519.SH",
                "platform": "weibo",
                "sentiment_score": -0.1,
            },
            {
                "trade_date": d1,
                "symbol": "000001.SZ",
                "platform": "guba",
                "sentiment_score": 0.05,
            },
        ],
    )
    store.append_many(
        "signal_history.jsonl",
        [
            {
                "trade_date": d1,
                "symbol": "600519.SH",
                "action": "BUY",
                "confidence": 0.4,
                "reason": "test",
                "platforms": ["guba"],
            }
        ],
    )
    store.append_many(
        "trade_history.jsonl",
        [
            {
                "trade_date": d1,
                "symbol": "600519.SH",
                "action": "BUY",
                "shares": 100,
                "price": 10.0,
                "note": "paper",
            }
        ],
    )
    store.append_many(
        "event_log.jsonl",
        [
            {
                "ts": f"{d1}T12:00:00",
                "event_type": "paper_fill",
                "trade_date": d1,
                "payload": {"symbol": "600519.SH", "action": "BUY"},
            }
        ],
    )


def test_query_memory_filters_symbol_and_dates(tmp_path):
    _seed_memory(tmp_path)
    rows = query_memory(
        str(tmp_path),
        kind="sentiment",
        symbol="600519.SH",
        limit=10,
    )
    assert len(rows) == 2
    assert all(r["symbol"] == "600519.SH" for r in rows)

    old = (date.today() - timedelta(days=5)).isoformat()
    recent = query_memory(
        str(tmp_path),
        kind="sentiment",
        symbol="600519.SH",
        start_date=old,
        end_date=(date.today() - timedelta(days=2)).isoformat(),
        limit=10,
    )
    assert len(recent) == 1
    assert recent[0]["sentiment_score"] == 0.2


def test_recall_symbol_context_summary(tmp_path):
    _seed_memory(tmp_path)
    ctx = recall_symbol_context(str(tmp_path), "600519.SH", lookback_days=7)
    assert ctx["symbol"] == "600519.SH"
    assert ctx["sentiment"]["row_count"] == 2
    assert ctx["signals"]["count"] == 1
    assert ctx["trades"]["count"] == 1
    assert ctx["events"]["count"] == 1


def test_recall_empty_dir(tmp_path):
    ctx = recall_symbol_context(str(tmp_path), "600519.SH")
    assert ctx["sentiment"]["row_count"] == 0
    assert ctx["signals"]["last"] is None


def test_resolve_recall_enabled_env_and_auto(tmp_path, monkeypatch):
    monkeypatch.delenv("MEMORY_RECALL", raising=False)
    cfg = MemoryRecallConfig(recall_enabled=False, recall_auto=True)
    assert resolve_recall_enabled(str(tmp_path), cfg) is False
    _seed_memory(tmp_path)
    assert memory_has_history(str(tmp_path))
    assert resolve_recall_enabled(str(tmp_path), cfg) is True
    monkeypatch.setenv("MEMORY_RECALL", "0")
    assert resolve_recall_enabled(str(tmp_path), cfg) is False


def test_apply_recall_to_signals():
    sig = TradeSignal(
        trade_date=date.today(),
        symbol="600519.SH",
        action="BUY",
        confidence=0.5,
        reason="x",
        platforms=["guba"],
    )
    ctx = {
        "600519.SH": {
            "lookback_days": 7,
            "sentiment": {"row_count": 2, "avg_score": 0.05},
            "signals": {"count": 1},
            "trades": {"count": 0},
        }
    }
    apply_recall_to_signals([sig], ctx, lang="zh")
    assert "历史记忆" in sig.explanation
    assert "情感均值" in format_recall_snippet(ctx["600519.SH"], lang="zh")


def test_prune_memory_jsonl(tmp_path):
    _seed_memory(tmp_path)
    removed = prune_memory_jsonl(str(tmp_path), keep_days=0)
    assert removed == {}
    removed = prune_memory_jsonl(str(tmp_path), keep_days=1)
    assert removed.get("sentiment", 0) >= 0


def test_cli_memory_query_smoke(tmp_path):
    _seed_memory(tmp_path)
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        f"project:\n  explanation_lang: zh\n"
        f"strategy:\n  platforms: [guba]\n  platform_weights: {{}}\n"
        f"  bearish_threshold: -0.6\n  bullish_threshold: 0.7\n"
        f"  min_platforms_for_signal: 1\n  reversal_min_delta: 0.1\n"
        f"  initial_cash: 100000\n  position_size_ratio: 0.2\n"
        f"universe:\n  symbols: [600519.SH]\n"
        f"storage:\n  memory_dir: {tmp_path}\n  report_dir: {tmp_path / 'reports'}\n",
        encoding="utf-8",
    )
    (tmp_path / "reports").mkdir()
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "opinion_trading.main",
            "--config",
            str(cfg),
            "--mode",
            "memory-recall",
            "--symbol",
            "600519.SH",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["symbol"] == "600519.SH"
