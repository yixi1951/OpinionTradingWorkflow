"""Sandbox broker fills, idempotency, reconcile, and stop-loss exits."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from opinion_trading.core.idempotency import IdempotencyStore
from opinion_trading.core.risk_controls import RiskLimits, generate_exit_signals
from opinion_trading.integrations.broker_adapter import ExecutionIntent, get_broker_adapter
from opinion_trading.integrations.sandbox_broker import SandboxBrokerAdapter


def test_sandbox_submit_and_reconcile(tmp_path: Path) -> None:
    mem = tmp_path / "memory"
    reports = tmp_path / "reports"
    broker = SandboxBrokerAdapter(
        str(reports),
        memory_dir=str(mem),
        initial_cash=100_000.0,
        slippage_bps=0.0,
        idempotency=IdempotencyStore(str(mem / "idempotency")),
    )
    intent = ExecutionIntent(
        trade_date="2026-06-17",
        symbol="AAA",
        side="BUY",
        confidence=0.9,
        suggested_notional_ratio=0.2,
        reason="test",
        dry_run=True,
        request_id="ord-test-1",
    )
    out = broker.submit_intents([intent], prices={"AAA": 10.0})
    assert out["count"] == 1
    pos = broker.fetch_positions()
    assert pos.get("AAA", 0) > 0

    # Duplicate request_id skipped
    out2 = broker.submit_intents([intent], prices={"AAA": 10.0})
    assert out2["skipped_duplicate"] == 1

    ok, mismatches = broker.reconcile(
        {"positions": pos, "cash": broker.fetch_ledger()["cash"]}
    )
    assert ok
    assert mismatches == []

    # Drift detection
    ok2, mm = broker.reconcile({"positions": {"AAA": 99999}})
    assert not ok2
    assert mm


def test_get_broker_adapter_sandbox(tmp_path: Path) -> None:
    adapter = get_broker_adapter(
        "sandbox",
        str(tmp_path / "reports"),
        memory_dir=str(tmp_path / "memory"),
    )
    assert isinstance(adapter, SandboxBrokerAdapter)


def test_generate_exit_signals_stop_and_take() -> None:
    limits = RiskLimits(stop_loss_pct=0.08, take_profit_pct=0.15)
    exits = generate_exit_signals(
        {"AAA": 100, "BBB": 50},
        {"AAA": 100.0, "BBB": 100.0},
        {"AAA": 90.0, "BBB": 120.0},
        trade_date=date(2026, 6, 17),
        limits=limits,
    )
    by_sym = {e.symbol: e for e in exits}
    assert "AAA" in by_sym
    assert "stop_loss" in by_sym["AAA"].reason
    assert "BBB" in by_sym
    assert "take_profit" in by_sym["BBB"].reason


def test_resolve_universe_constituents(tmp_path: Path) -> None:
    from opinion_trading.core.config_loader import _resolve_universe_symbols

    cfile = tmp_path / "c.json"
    cfile.write_text('["AAA", "BBB", "CCC"]', encoding="utf-8")
    syms = _resolve_universe_symbols(
        {
            "symbols": ["ZZZ", "AAA"],
            "constituents_file": str(cfile),
            "max_symbols": 3,
        },
        tmp_path / "settings.yaml",
    )
    assert syms[0] == "ZZZ"
    assert "AAA" in syms
    assert len(syms) == 3
