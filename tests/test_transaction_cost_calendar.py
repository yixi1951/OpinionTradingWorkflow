from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml

from opinion_trading.core.config_loader import load_runtime_config
from opinion_trading.core.evaluation import apply_fill_price, evaluate_signals
from opinion_trading.core.transaction_costs import (
    commission_bps_for_notional,
    load_transaction_cost_config,
    resolve_one_way_fee_bps,
    stamp_tax_bps_for_sell,
)


FIXTURE = Path(__file__).parent / "fixtures" / "transaction_cost_calendar.yaml"


def test_load_transaction_cost_config_disabled_by_default():
    cfg = load_transaction_cost_config({"execution": {}})
    assert cfg.enabled is False
    assert cfg.commission_tiers
    assert cfg.stamp_tax_calendar


def test_fixture_calendar_stamp_tax_step():
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    cfg = load_transaction_cost_config(raw)
    assert cfg.enabled is True
    assert stamp_tax_bps_for_sell(date(2023, 8, 27), cfg.stamp_tax_calendar) == 10.0
    assert stamp_tax_bps_for_sell(date(2023, 8, 28), cfg.stamp_tax_calendar) == 5.0


def test_commission_tier_picks_highest_matching():
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    cfg = load_transaction_cost_config(raw)
    assert commission_bps_for_notional(50_000, cfg.commission_tiers) == 3.0
    assert commission_bps_for_notional(100_000, cfg.commission_tiers) == 2.0


def test_resolve_fee_buy_vs_sell():
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    cfg = load_transaction_cost_config(raw)
    buy_bps = resolve_one_way_fee_bps(
        0.0,
        trade_date=date(2023, 8, 28),
        action="BUY",
        config=cfg,
        notional_cny=10_000,
    )
    sell_bps = resolve_one_way_fee_bps(
        0.0,
        trade_date=date(2023, 8, 28),
        action="SELL",
        config=cfg,
        notional_cny=10_000,
    )
    assert buy_bps == 3.0
    assert sell_bps == pytest.approx(8.0)


def test_apply_fill_price_sell_worse_with_stamp():
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    cfg = load_transaction_cost_config(raw)
    mid = 100.0
    buy = apply_fill_price(
        mid,
        "BUY",
        trade_date=date(2023, 8, 28),
        transaction_costs=cfg,
        notional_cny=10_000,
    )
    sell = apply_fill_price(
        mid,
        "SELL",
        trade_date=date(2023, 8, 28),
        transaction_costs=cfg,
        notional_cny=10_000,
    )
    assert sell < mid < buy


def test_evaluate_signals_sell_penalized_more_when_calendar_on():
    signals = pd.DataFrame(
        [
            {
                "trade_date": pd.Timestamp("2023-08-28"),
                "symbol": "600519.SH",
                "action": "SELL",
                "confidence": 0.8,
                "reason": "t",
                "platforms": ["guba"],
            },
        ]
    )
    prices = pd.DataFrame(
        [
            {"date": "2023-08-28", "symbol": "600519.SH", "close": 100.0},
            {"date": "2023-08-29", "symbol": "600519.SH", "close": 101.0},
        ]
    )
    raw = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    cfg = load_transaction_cost_config(raw)
    _, off = evaluate_signals(signals, prices, slippage_bps=0, fee_bps=0)
    _, on = evaluate_signals(
        signals, prices, slippage_bps=0, fee_bps=0, transaction_costs=cfg
    )
    assert on.avg_return <= off.avg_return


def test_runtime_config_includes_transaction_costs():
    runtime = load_runtime_config("config/settings.yaml")
    tx = runtime.execution.transaction_costs
    assert tx is not None
    assert tx.enabled is False
