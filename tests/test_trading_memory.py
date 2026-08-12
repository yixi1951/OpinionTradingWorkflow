"""Tests for cross-day trading memory."""

from __future__ import annotations

from datetime import date, datetime

from opinion_trading.core.memory_store import JsonLineMemoryStore
from opinion_trading.core.models import AggregatedSentiment, OpinionSnapshot, TradeSignal
from opinion_trading.core.trading_memory import (
    load_prior_from_raw_dir,
    load_prior_snapshots,
    load_symbol_memory,
    merge_snapshots_with_memory,
    prefer_history_then_raw,
    prior_date_count,
    row_to_snapshot,
    symbol_memory_as_rows,
    update_symbol_memory,
)
from opinion_trading.skills.sentiment_analysis import SentimentAnalysisSkill


def test_row_to_snapshot_and_prior_load(tmp_path):
    store = JsonLineMemoryStore(str(tmp_path))
    store.append_many(
        "sentiment_history.jsonl",
        [
            {
                "timestamp": "2026-05-12T10:00:00",
                "trade_date": "2026-05-12",
                "platform": "guba",
                "symbol": "600519.SH",
                "sentiment_score": -0.7,
                "post_count": 10,
                "source": "test",
            },
            {
                "timestamp": "2026-05-13T10:00:00",
                "trade_date": "2026-05-13",
                "platform": "guba",
                "symbol": "600519.SH",
                "sentiment_score": 0.2,
                "post_count": 8,
                "source": "test",
            },
        ],
    )
    prior = load_prior_snapshots(
        store, before=date(2026, 5, 13), symbols=["600519.SH"], lookback_days=30
    )
    assert len(prior) == 1
    assert prior[0].trade_date == date(2026, 5, 12)
    assert prior[0].sentiment_score == -0.7


def test_memory_enables_reversal_signal():
    skill = SentimentAnalysisSkill(
        bearish_threshold=-0.6,
        bullish_threshold=0.7,
        min_platforms_for_signal=2,
        reversal_min_delta=0.1,
        platform_weights={"guba": 1.0, "eastmoney": 1.0},
    )
    d0 = date(2026, 5, 12)
    d1 = date(2026, 5, 13)
    prior = [
        OpinionSnapshot(datetime.now(), d0, "guba", "600519.SH", -0.8, 5, "m"),
        OpinionSnapshot(datetime.now(), d0, "eastmoney", "600519.SH", -0.75, 5, "m"),
    ]
    today = [
        OpinionSnapshot(datetime.now(), d1, "guba", "600519.SH", -0.5, 5, "m"),
        OpinionSnapshot(datetime.now(), d1, "eastmoney", "600519.SH", -0.4, 5, "m"),
    ]
    # Without memory → no prev day → no BUY
    alone = skill.generate_signals(
        d1, skill.aggregate(today), platforms=["guba", "eastmoney"]
    )
    assert alone == []
    # With memory → pessimism reversal BUY
    merged = merge_snapshots_with_memory(today, prior)
    signals = skill.generate_signals(
        d1, skill.aggregate(merged), platforms=["guba", "eastmoney"]
    )
    assert len(signals) == 1
    assert signals[0].action == "BUY"
    assert signals[0].symbol == "600519.SH"


def test_symbol_memory_update_and_load(tmp_path):
    agg = {
        "600519.SH": AggregatedSentiment(
            trade_date=date(2026, 5, 13),
            symbol="600519.SH",
            platform_scores={"guba": 0.2, "eastmoney": 0.1},
        )
    }
    signals = [
        TradeSignal(
            trade_date=date(2026, 5, 13),
            symbol="600519.SH",
            action="BUY",
            confidence=0.7,
            reason="reversal",
            platforms=["guba", "eastmoney"],
        )
    ]
    update_symbol_memory(
        tmp_path,
        trade_date=date(2026, 5, 13),
        aggregated_today=agg,
        signals=signals,
        prior_day_count=3,
    )
    mem = load_symbol_memory(tmp_path)
    rows = symbol_memory_as_rows(mem)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "600519.SH"
    assert rows[0]["last_action"] == "BUY"
    assert mem["prior_days_used"] == 3


def test_prefer_history_then_raw_and_raw_hydrate(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    csv_path = raw_dir / "raw_posts_2026-05-12.csv"
    csv_path.write_text(
        "trade_date,platform,symbol,ai_score,keyword_score,is_noise,capture_status\n"
        "2026-05-12,guba,600519.SH,-0.5,0,0,success\n"
        "2026-05-12,eastmoney,600519.SH,-0.6,0,0,success\n",
        encoding="utf-8",
    )
    from_raw = load_prior_from_raw_dir(
        raw_dir, before=date(2026, 5, 13), symbols=["600519.SH"], lookback_days=30
    )
    assert prior_date_count(from_raw) == 1
    hist = [
        OpinionSnapshot(
            datetime.now(), date(2026, 5, 12), "guba", "600519.SH", -0.9, 9, "hist"
        )
    ]
    merged = prefer_history_then_raw(hist, from_raw)
    by_plat = {s.platform: s.sentiment_score for s in merged}
    assert by_plat["guba"] == -0.9  # history wins
    assert "eastmoney" in by_plat


def test_row_to_snapshot_rejects_bad():
    assert row_to_snapshot({}) is None
    assert row_to_snapshot({"trade_date": "2026-01-01", "symbol": "x"}) is None
