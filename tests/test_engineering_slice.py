"""Tests for cross-day dedup, sentiment winsorize, paper TP/SL, and broker stubs."""

from datetime import date

import pandas as pd
import pytest

from opinion_trading.core.cross_day_dedup import (
    CrossDayFingerprintStore,
    apply_cross_day_dedup,
)
from opinion_trading.core.models import (
    CrossDayDedupConfig,
    PaperExitConfig,
    SentimentWinsorizeConfig,
)
from opinion_trading.core.paper_exit_rules import (
    evaluate_paper_exits,
    record_entry_prices,
)
from opinion_trading.core.sentiment_winsorize import winsorize_raw_rows, winsorize_scores
from opinion_trading.core.models import PaperTrade
from opinion_trading.integrations.broker_adapter import (
    LiveBrokerAdapter,
    SandboxBrokerAdapter,
)


def _row(text: str, day: str = "2026-06-10") -> dict:
    return {
        "trade_date": day,
        "platform": "guba",
        "symbol": "000001.SZ",
        "title": text,
        "content": text,
        "capture_status": "success",
    }


def test_cross_day_dedup_filters_repeat_across_days(tmp_path):
    db = tmp_path / "fp.sqlite"
    cfg = CrossDayDedupConfig(enabled=True, db_path=str(db), lookback_days=30)
    store = CrossDayFingerprintStore(str(db))
    day1 = date(2026, 6, 10)
    day2 = date(2026, 6, 11)
    rows = [_row("same post body")]
    kept1, stats1 = apply_cross_day_dedup(rows, trade_date=day1, config=cfg, store=store)
    assert len(kept1) == 1
    assert stats1["registered"] >= 1
    kept2, stats2 = apply_cross_day_dedup(rows, trade_date=day2, config=cfg, store=store)
    assert len(kept2) == 0
    assert stats2["removed"] == 1


def test_cross_day_dedup_disabled_is_noop(tmp_path):
    cfg = CrossDayDedupConfig(enabled=False, db_path=str(tmp_path / "x.sqlite"))
    rows = [_row("a"), _row("b")]
    out, stats = apply_cross_day_dedup(rows, trade_date=date(2026, 6, 10), config=cfg)
    assert out == rows
    assert stats["removed"] == 0


def test_winsorize_clips_extremes_not_mid():
    scores = [-0.99, -0.1, 0.0, 0.1, 0.05, 0.99]
    out = winsorize_scores(scores, lower_pct=10.0, upper_pct=90.0)
    assert out[1] == pytest.approx(-0.1)
    assert out[3] == pytest.approx(0.1)
    assert out[0] > -0.99
    assert out[-1] < 0.99


def test_winsorize_raw_rows_disabled():
    rows = [{"ai_score": 0.95}, {"ai_score": -0.95}]
    cfg = SentimentWinsorizeConfig(enabled=False)
    assert winsorize_raw_rows(rows, config=cfg) == rows


def test_winsorize_raw_rows_enabled():
    rows = [
        {"ai_score": -0.99},
        {"ai_score": 0.0},
        {"ai_score": 0.99},
        {"ai_score": 0.01},
    ]
    cfg = SentimentWinsorizeConfig(enabled=True, lower_pct=25.0, upper_pct=75.0)
    out = winsorize_raw_rows(rows, config=cfg)
    vals = [r["ai_score"] for r in out]
    assert max(vals) < 0.99
    assert min(vals) > -0.99
    assert 0.0 in vals


def test_paper_take_profit_emits_sell(tmp_path):
    mem = tmp_path / "mem"
    mem.mkdir()
    price_df = pd.DataFrame(
        [
            {"date": "2026-06-10", "symbol": "000001.SZ", "close": 11.0},
            {"date": "2026-06-11", "symbol": "000001.SZ", "close": 12.5},
        ]
    )
    record_entry_prices(
        str(mem),
        [
            PaperTrade(
                trade_date=date(2026, 6, 10),
                symbol="000001.SZ",
                action="BUY",
                shares=100,
                price=10.0,
                cash_after=0.0,
                note="",
            )
        ],
        {"000001.SZ": 100},
    )
    state = {"cash": 0.0, "positions": {"000001.SZ": 100}}
    cfg = PaperExitConfig(enabled=True, take_profit_pct=0.10, stop_loss_pct=0.05)
    signals, diag = evaluate_paper_exits(
        date(2026, 6, 11),
        state,
        price_df=price_df,
        config=cfg,
        memory_dir=str(mem),
    )
    assert len(signals) == 1
    assert signals[0].action == "SELL"
    assert "take_profit" in signals[0].reason
    assert diag[0]["pnl_pct"] >= 0.10


def test_paper_stop_loss_emits_sell(tmp_path):
    mem = tmp_path / "mem"
    mem.mkdir()
    price_df = pd.DataFrame(
        [{"date": "2026-06-12", "symbol": "600519.SH", "close": 90.0}]
    )
    record_entry_prices(
        str(mem),
        [
            PaperTrade(
                trade_date=date(2026, 6, 10),
                symbol="600519.SH",
                action="BUY",
                shares=10,
                price=100.0,
                cash_after=0.0,
                note="",
            )
        ],
        {"600519.SH": 10},
    )
    state = {"positions": {"600519.SH": 10}}
    cfg = PaperExitConfig(enabled=True, take_profit_pct=0.20, stop_loss_pct=0.05)
    signals, _ = evaluate_paper_exits(
        date(2026, 6, 12),
        state,
        price_df=price_df,
        config=cfg,
        memory_dir=str(mem),
    )
    assert signals and signals[0].action == "SELL"
    assert "stop_loss" in signals[0].reason


def test_live_broker_stub_raises():
    live = LiveBrokerAdapter()
    with pytest.raises(NotImplementedError):
        live.submit_intents([])
    with pytest.raises(NotImplementedError):
        live.fetch_account()


def test_sandbox_still_dry_run(tmp_path):
    from opinion_trading.integrations.broker_adapter import ExecutionIntent

    broker = SandboxBrokerAdapter(str(tmp_path))
    intents = [
        ExecutionIntent(
            trade_date="2026-06-10",
            symbol="000001.SZ",
            side="BUY",
            confidence=0.8,
            suggested_notional_ratio=0.1,
            reason="test",
        )
    ]
    out = broker.submit_intents(intents)
    assert out.get("live_order") is False
