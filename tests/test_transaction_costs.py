from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from opinion_trading.core.evaluation import (
    apply_fill_price,
    evaluate_signals,
    transaction_cost_fraction,
)
from opinion_trading.core.models import AggregatedSentiment, TradeSignal
from opinion_trading.skills.trade_simulation import PaperTradingSkill


def test_transaction_cost_fraction():
    assert transaction_cost_fraction(0, 0) == 0.0
    assert transaction_cost_fraction(50, 50) == pytest.approx(0.01)


def test_apply_fill_price_buy_sell():
    mid = 100.0
    buy = apply_fill_price(mid, "BUY", slippage_bps=50, fee_bps=50)
    sell = apply_fill_price(mid, "SELL", slippage_bps=50, fee_bps=50)
    assert buy == pytest.approx(101.0)
    assert sell == pytest.approx(99.0)
    assert apply_fill_price(mid, "BUY") == mid


def test_evaluate_signals_fees_reduce_strategy_return():
    signals = pd.DataFrame(
        [
            {
                "trade_date": pd.Timestamp("2026-05-01"),
                "symbol": "600519.SH",
                "action": "BUY",
                "confidence": 0.8,
                "reason": "t",
                "platforms": ["guba"],
            },
            {
                "trade_date": pd.Timestamp("2026-05-02"),
                "symbol": "600519.SH",
                "action": "SELL",
                "confidence": 0.7,
                "reason": "t",
                "platforms": ["guba"],
            },
        ]
    )
    prices = pd.DataFrame(
        [
            {"date": "2026-05-01", "symbol": "600519.SH", "close": 100.0},
            {"date": "2026-05-02", "symbol": "600519.SH", "close": 110.0},
            {"date": "2026-05-03", "symbol": "600519.SH", "close": 99.0},
        ]
    )
    merged0, sum0 = evaluate_signals(signals, prices)
    merged1, sum1 = evaluate_signals(signals, prices, slippage_bps=100, fee_bps=100)
    assert sum0.total_signals == sum1.total_signals == 2
    assert "strategy_return" in merged0.columns
    assert float(merged1["strategy_return"].mean()) < float(merged0["strategy_return"].mean())
    assert sum1.profit_factor <= sum0.profit_factor


def test_paper_fills_cost_more_when_fees_enabled():
    agg = AggregatedSentiment(
        trade_date=date(2026, 6, 17),
        symbol="600519.SH",
        platform_scores={"guba": 0.4},
    )
    signal = TradeSignal(
        trade_date=date(2026, 6, 17),
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        reason="fee-test",
        platforms=["guba"],
    )
    prices = pd.DataFrame(
        [{"date": "2026-06-17", "symbol": "600519.SH", "close": 100.0}]
    )
    state0 = {"cash": 100_000.0, "positions": {}, "last_run_date": "2026-06-17"}
    skill0 = PaperTradingSkill(
        100_000.0, 0.2, use_market_prices=True, price_df=prices, slippage_bps=0, fee_bps=0
    )
    skill1 = PaperTradingSkill(
        100_000.0,
        0.2,
        use_market_prices=True,
        price_df=prices,
        slippage_bps=100,
        fee_bps=100,
    )
    today = {"600519.SH": agg}
    trades0, st0 = skill0.simulate(date(2026, 6, 17), [signal], today, dict(state0))
    trades1, st1 = skill1.simulate(date(2026, 6, 17), [signal], today, dict(state0))
    assert trades0 and trades1
    assert trades1[0].price > trades0[0].price
    eq0 = skill0.portfolio_value(today, st0)
    eq1 = skill1.portfolio_value(today, st1)
    assert eq1 < eq0
