"""Observability: ops alerts + pipeline metrics."""

from __future__ import annotations

import json

from opinion_trading.core.alert_notifier import AlertNotifier, ops_alerts_enabled
from opinion_trading.core.pipeline_metrics import (
    PipelineMetrics,
    record_daily_snapshot,
)


def test_ops_alert_format_and_skip(monkeypatch):
    monkeypatch.setenv("OPS_ALERTS_ENABLED", "1")
    monkeypatch.delenv("DINGTALK_WEBHOOK", raising=False)
    monkeypatch.delenv("WECOM_WEBHOOK", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    n = AlertNotifier()
    out = n.push_ops_alert(
        "trading_halted",
        severity="critical",
        summary="max_daily_loss",
        trade_date="2026-07-22",
        halt_reason="max_daily_loss",
    )
    assert out["dingtalk"]["enabled"] is False
    assert "skipped" not in out

    monkeypatch.setenv("OPS_ALERTS_ENABLED", "0")
    assert ops_alerts_enabled() is False
    skipped = n.push_ops_alert("broker_failure", summary="x")
    assert skipped.get("skipped") is True


def test_ops_message_contains_kind():
    n = AlertNotifier()
    msg = n._format_message(
        {
            "kind": "risk_reject",
            "severity": "warning",
            "summary": "2 rejected",
            "trade_date": "2026-07-22",
            "env": "staging",
            "reject_count": 2,
        }
    )
    assert "OPS/WARNING" in msg
    assert "kind=risk_reject" in msg
    assert "reject_count=2" in msg


def test_pipeline_metrics_flush(tmp_path):
    m = PipelineMetrics()
    record_daily_snapshot(
        m,
        trade_date="2026-07-22",
        signals=5,
        signals_allowed=3,
        risk_rejects=2,
        trades=1,
        open_positions=2,
        pending_orders=0,
        trading_halted=True,
        broker_errors=1,
        portfolio_value=99_000.0,
    )
    paths = m.flush(str(tmp_path))
    prom = (tmp_path / "pipeline_metrics.prom").read_text(encoding="utf-8")
    assert "pipeline_risk_rejects_total" in prom
    assert "pipeline_trading_halted" in prom
    data = json.loads((tmp_path / "pipeline_metrics.json").read_text(encoding="utf-8"))
    assert data["gauges"]["pipeline_trading_halted"] == 1.0
    assert data["counters"]["pipeline_risk_rejects_total"] == 2.0
    assert paths["prom"].endswith("pipeline_metrics.prom")
