from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from opinion_trading.core.backtest import StrategyBacktester


class FakeCollector:
    def collect_for_days(self, symbols, platforms, trade_date, lookback_days=1):
        return [
            SimpleNamespace(
                trade_date=trade_date,
                symbol=symbols[0],
                platform=platforms[0],
                sentiment_score=-0.9 if trade_date.day == 1 else 0.9,
                post_count=1,
                source="stub",
                to_dict=lambda: {},
            )
        ]


@pytest.fixture
def backtester(monkeypatch):
    fake_config = SimpleNamespace(
        strategy=SimpleNamespace(
            min_platforms_for_signal=1,
            reversal_min_delta=0.1,
            initial_cash=1000.0,
            position_size_ratio=0.5,
            bullish_threshold=0.6,
            platforms=["guba"],
            platform_weights={"guba": 1.0},
        ),
        symbols=["600519.SH"],
    )

    monkeypatch.setattr("opinion_trading.core.backtest.load_runtime_config", lambda _: fake_config)
    bt = StrategyBacktester(config_path="dummy.yaml")
    bt.collector = FakeCollector()
    return bt


def test_parse_date():
    assert StrategyBacktester.parse_date("2026-05-30") == date(2026, 5, 30)


def test_run_single_and_save_results(tmp_path, backtester):
    result = backtester.run_single(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 2),
        bearish_threshold=-0.6,
        bullish_threshold=0.6,
        platforms=["guba"],
    )

    assert result.platforms == ["guba"]
    assert isinstance(result.final_equity, float)

    out = tmp_path / "results.csv"
    backtester.save_results([result], str(out))
    content = out.read_text(encoding="utf-8")
    assert "bearish_threshold" in content
    assert "guba" in content
