from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from opinion_trading.agents.workflow import OpinionTradingWorkflow


class StubCollectorAgent:
    def __init__(self):
        self.calls = 0

    def run(self, symbols, platforms, trade_date):
        self.calls += 1
        score = -0.8 if self.calls == 1 else 0.2
        return [
            SimpleNamespace(
                timestamp=None,
                trade_date=trade_date,
                platform=platforms[0],
                symbol=symbols[0],
                sentiment_score=score,
                post_count=3,
                source="stub",
                to_dict=lambda: {
                    "trade_date": trade_date.isoformat(),
                    "platform": platforms[0],
                    "symbol": symbols[0],
                    "sentiment_score": score,
                    "post_count": 3,
                    "source": "stub",
                },
            )
        ]


class StubAnalystAgent:
    def run(self, trade_date, snapshots, platforms):
        aggregated = {
            trade_date: {
                "600519.SH": SimpleNamespace(
                    trade_date=trade_date,
                    symbol="600519.SH",
                    platform_scores={platforms[0]: snapshots[0].sentiment_score},
                    average_score=snapshots[0].sentiment_score,
                )
            }
        }
        return [], aggregated, [platforms[0]], {platforms[0]: snapshots[0].sentiment_score}


class StubStore:
    def __init__(self):
        self.saved = {}

    def append_many(self, file_name, records):
        self.saved.setdefault(file_name, []).extend(records)

    def load_state(self, file_name="state.json"):
        return {"cash": 1000.0, "positions": {}}

    def save_state(self, state, file_name="state.json"):
        self.saved[file_name] = state


class StubAlertNotifier:
    def push_alert(self, alert):
        return {"enabled": False, "ok": False, "detail": "stub"}


@pytest.fixture
def workflow(monkeypatch, tmp_path):
    fake_config = SimpleNamespace(
        strategy=SimpleNamespace(
            platforms=["guba"],
            platform_weights={"guba": 1.0},
            bearish_threshold=-0.6,
            bullish_threshold=0.6,
            min_platforms_for_signal=1,
            reversal_min_delta=0.1,
            initial_cash=1000.0,
            position_size_ratio=0.1,
        ),
        symbols=["600519.SH"],
        memory_dir=str(tmp_path / "memory"),
        report_dir=str(tmp_path / "reports"),
        raw_dir=str(tmp_path / "raw"),
    )
    monkeypatch.setattr("opinion_trading.agents.workflow.load_runtime_config", lambda _: fake_config)
    wf = OpinionTradingWorkflow(config_path="dummy.yaml")
    wf.collector = StubCollectorAgent()
    wf.analyst = StubAnalystAgent()
    wf.store = StubStore()
    wf.alert_notifier = StubAlertNotifier()
    monkeypatch.setattr("opinion_trading.agents.workflow.sleep", lambda _: None)
    return wf


def test_run_realtime_single_iteration(workflow):
    result = workflow.run_realtime(iterations=2, interval_seconds=0, top_n=1, alert_threshold=0.1)

    assert result["mode"] == "realtime"
    assert result["iterations"] == 2
    assert result["picks"]
    assert result["best_combo"] == ["guba"]
    assert result["report_csv"].endswith(".csv")
    assert result["report_md"].endswith(".md")
