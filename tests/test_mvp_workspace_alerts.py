"""MVP: user workspace, watchlist alerts, explainability."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from opinion_trading.core.symbol_explain import explain_symbol_sentiment
from opinion_trading.core.user_workspace import AlertRule, UserWorkspace
from opinion_trading.core.watchlist_alerts import (
    dispatch_alert_event,
    evaluate_user_alerts,
    run_watchlist_alert_cycle,
)


@pytest.fixture()
def ws(tmp_path: Path) -> UserWorkspace:
    return UserWorkspace(root=str(tmp_path / "users"))


def test_demo_user_and_auth(ws: UserWorkspace) -> None:
    demo = ws.authenticate("demo", "demo123")
    assert demo is not None
    assert "600519.SH" in demo.watchlist
    assert ws.authenticate("demo", "wrong") is None


def test_register_watchlist_and_inbox(ws: UserWorkspace) -> None:
    p = ws.register("alice", "secret", email="a@example.com")
    assert p.email == "a@example.com"
    with pytest.raises(ValueError):
        ws.register("alice", "x")

    wl = ws.add_watch("alice", "000001.sz")
    assert "000001.SZ" in wl
    ws.remove_watch("alice", "000001.SZ")
    assert "000001.SZ" not in (ws.load_profile("alice").watchlist or [])

    ws.upsert_alert_rule(
        "alice",
        AlertRule(symbol="600519.SH", score_high=0.2, score_low=-0.2),
    )
    prof = ws.load_profile("alice")
    assert any(r["symbol"] == "600519.SH" for r in prof.alert_rules)
    assert "600519.SH" in prof.watchlist

    ws.push_inbox("alice", {"title": "t1", "type": "alert"})
    inbox = ws.list_inbox("alice")
    assert len(inbox) == 1
    assert inbox[0]["read"] is False
    ws.mark_inbox_read("alice")
    assert ws.list_inbox("alice")[0]["read"] is True


def _sentiment_two_days(score_latest: float, heat_latest: float = 100) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "trade_date": "2026-07-20",
                "sentiment_score": 0.1,
                "post_count": 10,
            },
            {
                "symbol": "600519.SH",
                "trade_date": "2026-07-21",
                "sentiment_score": score_latest,
                "post_count": heat_latest,
            },
        ]
    )


def test_evaluate_alerts_score_and_heat(ws: UserWorkspace) -> None:
    ws.upsert_alert_rule(
        "demo",
        AlertRule(symbol="600519.SH", score_high=0.3, score_low=-0.3, heat_spike_ratio=2.0),
    )
    high = evaluate_user_alerts("demo", _sentiment_two_days(0.5, heat_latest=10), workspace=ws)
    assert len(high) == 1
    assert any("≥" in r for r in high[0]["reasons"])

    heat = evaluate_user_alerts(
        "demo", _sentiment_two_days(0.0, heat_latest=50), workspace=ws
    )
    assert len(heat) == 1
    assert any("热度" in r for r in heat[0]["reasons"])

    quiet = evaluate_user_alerts(
        "demo", _sentiment_two_days(0.0, heat_latest=10), workspace=ws
    )
    assert quiet == []


def test_dispatch_writes_inbox(ws: UserWorkspace, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("WECOM_WEBHOOK", raising=False)
    monkeypatch.delenv("DINGTALK_WEBHOOK", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    event = {
        "username": "demo",
        "symbol": "600519.SH",
        "score": 0.5,
        "heat": 20,
        "trade_date": "2026-07-21",
        "reasons": ["情感分过高"],
        "severity": "yellow",
        "direction": "up",
        "previous_score": 0.1,
        "current_score": 0.5,
        "delta": 0.4,
        "time": "2026-07-22T12:00:00",
    }
    out = dispatch_alert_event(event, email="", workspace=ws)
    assert out["inbox"] is True
    assert out["email"]["enabled"] is False
    assert ws.list_inbox("demo")


def test_run_alert_cycle(ws: UserWorkspace, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    ws.upsert_alert_rule(
        "demo",
        AlertRule(symbol="600519.SH", score_high=0.25, score_low=-0.25),
    )
    results = run_watchlist_alert_cycle(
        "demo", _sentiment_two_days(0.4), workspace=ws
    )
    assert len(results) == 1
    assert results[0]["dispatch"]["inbox"] is True


def test_explain_symbol_sentiment() -> None:
    sentiment = pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "trade_date": "2026-07-21",
                "sentiment_score": 0.42,
                "platform": "xueqiu",
            }
        ]
    )
    raw = pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "platform": "xueqiu",
                "title": "业绩超预期大涨",
                "content": "茅台财报亮眼，机构看多",
                "ai_score": 0.8,
            }
        ]
    )
    expl = explain_symbol_sentiment(
        "600519.SH", sentiment_df=sentiment, raw_df=raw, top_k=3
    )
    assert expl["score"] is not None
    assert expl["score"] > 0
    assert "summary" in expl and expl["summary"]
    assert expl["direction"]
