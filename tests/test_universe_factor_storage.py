from __future__ import annotations

import pandas as pd

from opinion_trading.core.factor_backtest import (
    attach_forward_returns,
    group_quantile_excess,
    neutralize_factor,
    run_factor_backtest,
)
from opinion_trading.core.noise_filter import filter_noisy_rows, is_spam_or_ad, is_water_post
from opinion_trading.core.quality_monitor import evaluate_quality_monitor
from opinion_trading.core.signal_weights import combined_post_weight, event_weight
from opinion_trading.core.storage import FileStorage, get_storage
from opinion_trading.core.symbol_map import SymbolMapper
from opinion_trading.core.universe import load_index_constituents


def test_symbol_mapper_maotai():
    m = SymbolMapper()
    ok, tokens = m.match_symbol("今天茅台放量了", "600519.SH")
    assert ok
    assert tokens
    hits = m.resolve("宁德时代和隆基都在调整")
    syms = {h[0] for h in hits}
    assert "300750.SZ" in syms
    assert "601012.SH" in syms


def test_ambiguous_pingan_not_alone():
    m = SymbolMapper()
    # bare 平安 is ambiguous — should not uniquely resolve without fuller alias
    hits = m.resolve("平安")
    # may be empty or multiple; must not silently map only via ambiguous token alone
    assert all(tok != "平安" or sym in {"601318.SH", "000001.SZ"} for sym, tok in hits)


def test_universe_focus_offline():
    symbols = load_index_constituents("hs300", max_symbols=8, use_akshare=False)
    assert 1 <= len(symbols) <= 8
    assert all("." in s for s in symbols)


def test_noise_filter_spam_and_water():
    assert is_spam_or_ad("加微信稳赚不赔")
    assert is_water_post("哈哈哈哈")
    rows, stats = filter_noisy_rows(
        [
            {"title": "茅台看好", "content": "业绩超预期"},
            {"title": "广告", "content": "加微信免费荐股"},
            {"title": "666", "content": "666"},
        ]
    )
    assert stats["noise_rate"] >= 0.3
    assert any(r.get("is_noise") for r in rows)


def test_quality_monitor_thresholds():
    rows = [
        {
            "title": "t",
            "post_time": "2026-01-01",
            "content": "贵州茅台上涨",
            "is_noise": False,
            "entity_matched": True,
            "capture_status": "success",
            "authority_grade": "high",
            "content_kind": "comment",
        }
        for _ in range(10)
    ]
    result = evaluate_quality_monitor(rows, trade_date="2026-01-01")
    assert result.metrics["noise_rate"] == 0.0
    assert result.ok or "entity_match" not in str(result.alerts)


def test_event_and_user_weights():
    assert event_weight("earnings") > event_weight("rumor")
    w = combined_post_weight(
        {
            "authority_weight": 1.1,
            "event_type": "earnings",
            "authority_grade": "high",
            "author": "认证分析师",
            "title": "研报点评",
        }
    )
    assert w > 1.0


def test_factor_backtest_lead_lag(tmp_path):
    prices = pd.DataFrame(
        [
            {"date": "2026-01-02", "symbol": "600519.SH", "close": 100.0},
            {"date": "2026-01-03", "symbol": "600519.SH", "close": 102.0},
            {"date": "2026-01-06", "symbol": "600519.SH", "close": 101.0},
            {"date": "2026-01-07", "symbol": "600519.SH", "close": 103.0},
            {"date": "2026-01-02", "symbol": "000001.SZ", "close": 10.0},
            {"date": "2026-01-03", "symbol": "000001.SZ", "close": 9.8},
            {"date": "2026-01-06", "symbol": "000001.SZ", "close": 9.9},
            {"date": "2026-01-07", "symbol": "000001.SZ", "close": 10.1},
            {"date": "2026-01-02", "symbol": "600036.SH", "close": 40.0},
            {"date": "2026-01-03", "symbol": "600036.SH", "close": 40.5},
            {"date": "2026-01-06", "symbol": "600036.SH", "close": 41.0},
            {"date": "2026-01-07", "symbol": "600036.SH", "close": 40.8},
        ]
    )
    prices = attach_forward_returns(prices, horizons=(1, 3))
    assert "ret_1d" in prices.columns
    factor = pd.DataFrame(
        [
            {"trade_date": "2026-01-02", "symbol": "600519.SH", "factor": 0.8},
            {"trade_date": "2026-01-02", "symbol": "000001.SZ", "factor": -0.5},
            {"trade_date": "2026-01-02", "symbol": "600036.SH", "factor": 0.2},
            {"trade_date": "2026-01-03", "symbol": "600519.SH", "factor": 0.6},
            {"trade_date": "2026-01-03", "symbol": "000001.SZ", "factor": -0.2},
            {"trade_date": "2026-01-03", "symbol": "600036.SH", "factor": 0.1},
        ]
    )
    factor["trade_date"] = pd.to_datetime(factor["trade_date"])
    # neutralization smoke
    factor["factor_n"] = neutralize_factor(factor, factor_col="factor")
    merged_g = factor.merge(
        prices[["date", "symbol", "ret_1d"]],
        left_on=["trade_date", "symbol"],
        right_on=["date", "symbol"],
    )
    groups = group_quantile_excess(
        merged_g,
        factor_col="factor",
        return_col="ret_1d",
        n_groups=3,
    )
    assert "long_short" in groups

    report = run_factor_backtest(
        factor, prices, horizons=(1, 3), neutralize=True, n_groups=3
    )
    assert 1 in report.horizons
    assert report.n_obs > 0


def test_file_storage_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "file")
    store = get_storage()
    assert isinstance(store, FileStorage) or store is not None
    fs = FileStorage(str(tmp_path / "db"))
    n = fs.save_structured("scores", [{"symbol": "600519.SH", "score": 0.1}])
    assert n == 1
    fs.cache_set("k", {"v": 1})
    assert fs.cache_get("k")["v"] == 1
