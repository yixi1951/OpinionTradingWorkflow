"""Failure-path + production-readiness tests (P0/P1)."""

from __future__ import annotations

from datetime import date

import pytest

from opinion_trading.core.models import TradeSignal
from opinion_trading.core.http_retry import retry_with_backoff


def test_kill_switch_halts_all(monkeypatch):
    from opinion_trading.core.risk_controls import RiskLimits, apply_risk_to_signals, is_trading_halted

    monkeypatch.setenv("KILL_SWITCH", "1")
    halted, reason = is_trading_halted({})
    assert halted and "kill_switch" in reason
    sig = TradeSignal(
        trade_date=date(2026, 6, 1),
        symbol="600519.SH",
        action="BUY",
        confidence=0.9,
        reason="x",
        platforms=["guba"],
        kelly_fraction=0.1,
    )
    out = apply_risk_to_signals(
        [sig],
        portfolio_value=100_000,
        cash=100_000,
        positions={},
        limits=RiskLimits(),
        trading_already_halted=True,
        halt_reason=reason,
    )
    assert out.trading_halted
    assert len(out.rejected) == 1


def test_max_concurrent_orders():
    from opinion_trading.core.risk_controls import RiskLimits, apply_risk_to_signals

    signals = [
        TradeSignal(
            trade_date=date(2026, 6, 1),
            symbol=f"00000{i}.SZ",
            action="BUY",
            confidence=0.8,
            reason="x",
            platforms=["guba"],
            kelly_fraction=0.05,
        )
        for i in range(5)
    ]
    out = apply_risk_to_signals(
        signals,
        portfolio_value=100_000,
        cash=100_000,
        positions={},
        limits=RiskLimits(max_concurrent_orders=2, max_open_positions=10),
        pending_order_count=0,
    )
    assert len(out.allowed) == 2
    assert all(r[1] == "max_concurrent_orders" for r in out.rejected)


def test_daily_loss_halt():
    from opinion_trading.core.risk_controls import RiskLimits, apply_risk_to_signals

    sig = TradeSignal(
        trade_date=date(2026, 6, 1),
        symbol="600519.SH",
        action="BUY",
        confidence=0.9,
        reason="x",
        platforms=["guba"],
        kelly_fraction=0.05,
    )
    out = apply_risk_to_signals(
        [sig],
        portfolio_value=90_000,
        cash=90_000,
        positions={},
        limits=RiskLimits(max_daily_loss_pct=0.05),
        day_start_equity=100_000,
    )
    assert out.trading_halted
    assert "max_daily_loss" in out.halt_reason


def test_order_idempotency_no_double_submit(tmp_path):
    from opinion_trading.integrations.broker_adapter import (
        ExecutionIntent,
        PaperBrokerAdapter,
    )
    from opinion_trading.core.idempotency import IdempotencyStore
    from opinion_trading.core.audit_log import AuditLogger

    store = IdempotencyStore(str(tmp_path / "idem"))
    audit = AuditLogger(str(tmp_path / "audit.jsonl"))
    broker = PaperBrokerAdapter(
        str(tmp_path / "reports"), idempotency=store, audit=audit
    )
    intent = ExecutionIntent(
        trade_date="2026-06-01",
        symbol="600519.SH",
        side="BUY",
        confidence=0.8,
        suggested_notional_ratio=0.1,
        reason="test",
        request_id="ord-fixed-key-1",
        event_id="evt-1",
        trace_id="tr-1",
        order_id="ord-fixed-key-1",
    )
    r1 = broker.submit_intents([intent])
    r2 = broker.submit_intents([intent])
    assert r1["count"] == 1
    assert r2["count"] == 0
    assert r2["skipped_duplicate"] == 1


def test_replay_duplicate_signal_event(tmp_path):
    from opinion_trading.core.idempotency import IdempotencyStore

    store = IdempotencyStore(str(tmp_path))
    assert store.remember("signals", "evt-abc", payload={"x": 1}) is True
    assert store.remember("signals", "evt-abc", payload={"x": 1}) is False


def test_retry_backoff_on_5xx_like_errors():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("simulated disconnect")
        return "ok"

    assert retry_with_backoff(flaky, max_attempts=4, base_delay=0.01, max_delay=0.05) == "ok"
    assert calls["n"] == 3


def test_retry_gives_up_on_persistent_timeout():
    def always_timeout():
        raise TimeoutError("network timeout")

    with pytest.raises(TimeoutError):
        retry_with_backoff(
            always_timeout, max_attempts=2, base_delay=0.01, max_delay=0.02
        )


def test_http_429_style_should_retry():
    calls = {"n": 0}

    class RateLimitError(Exception):
        status = 429

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RateLimitError("429 too many")
        return 42

    assert (
        retry_with_backoff(
            flaky,
            max_attempts=3,
            base_delay=0.01,
            retry_on=(RateLimitError,),
        )
        == 42
    )


def test_config_validation_rejects_bad_risk(monkeypatch):
    from opinion_trading.core.models import RiskConfig, RuntimeConfig, StrategyConfig
    from opinion_trading.core.config_validate import validate_runtime_config

    cfg = RuntimeConfig(
        strategy=StrategyConfig(
            platforms=["guba"],
            platform_weights={"guba": 1.0},
            bearish_threshold=-0.2,
            bullish_threshold=0.2,
            min_platforms_for_signal=1,
            reversal_min_delta=0.1,
            initial_cash=100000,
            position_size_ratio=0.2,
        ),
        symbols=["600519.SH"],
        memory_dir="data/memory",
        report_dir="data/reports",
        raw_dir="data/raw",
        risk=RiskConfig(max_daily_loss_pct=0.0),
    )
    result = validate_runtime_config(cfg)
    assert not result.ok


def test_ws_resume_cursor_roundtrip(tmp_path):
    from opinion_trading.openclaw_proxy.connection import ResumeCursor, HeartbeatMonitor

    path = tmp_path / "cursor.json"
    c = ResumeCursor()
    c.mark_sent("req-1")
    c.mark_acked("evt-1")
    c.save(path)
    loaded = ResumeCursor.load(path)
    assert loaded.resume_from() == "evt-1"
    hb = HeartbeatMonitor(interval_sec=1, timeout_sec=0.01)
    hb.last_pong_at = 0.0
    assert hb.is_stale()


def test_missing_market_data_does_not_crash_risk():
    from opinion_trading.core.risk_controls import RiskLimits, apply_risk_to_signals

    sig = TradeSignal(
        trade_date=date(2026, 6, 1),
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        reason="delayed",
        platforms=["guba"],
        kelly_fraction=0.05,
    )
    out = apply_risk_to_signals(
        [sig],
        portfolio_value=100_000,
        cash=100_000,
        positions={},
        limits=RiskLimits(),
        reference_prices={},  # missing / delayed prices
    )
    assert len(out.allowed) == 1


def test_audit_trail_jsonl(tmp_path):
    from opinion_trading.core.audit_log import AuditLogger
    import json

    path = tmp_path / "audit.jsonl"
    log = AuditLogger(str(path))
    row = log.emit(
        "decision_to_order",
        trace_id="tr-1",
        order_id="ord-1",
        symbol="600519.SH",
        reason="bullish",
    )
    assert row["trace_id"] == "tr-1"
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "decision_to_order"


def test_minimal_integration_paper_submit(tmp_path, monkeypatch):
    """Minimal integration: signal → intent → idempotent paper submit → audit."""
    monkeypatch.setenv("KILL_SWITCH", "0")
    from opinion_trading.integrations.broker_adapter import trade_signals_to_intents, PaperBrokerAdapter
    from opinion_trading.core.idempotency import IdempotencyStore
    from opinion_trading.core.audit_log import AuditLogger
    from opinion_trading.core.risk_controls import RiskLimits, apply_risk_to_signals

    sig = TradeSignal(
        trade_date=date(2026, 6, 17),
        symbol="600519.SH",
        action="BUY",
        confidence=0.7,
        reason="integration",
        platforms=["guba"],
        kelly_fraction=0.05,
    )
    risk = apply_risk_to_signals(
        [sig],
        portfolio_value=100_000,
        cash=100_000,
        positions={},
        limits=RiskLimits(max_concurrent_orders=3),
    )
    intents = trade_signals_to_intents(risk.allowed, dry_run=True)
    broker = PaperBrokerAdapter(
        str(tmp_path / "r"),
        idempotency=IdempotencyStore(str(tmp_path / "i")),
        audit=AuditLogger(str(tmp_path / "a.jsonl")),
    )
    out = broker.submit_intents(intents)
    assert out["count"] == 1
    out2 = broker.submit_intents(intents)
    assert out2["skipped_duplicate"] == 1
