"""Unit tests for bullishness, sentiment panel, FM and Logit."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from opinion_trading.core.bullishness import (
    antweiler_agreement,
    antweiler_bullishness,
    bullishness_from_rows,
)
from opinion_trading.core.direction_logit import run_direction_logit
from opinion_trading.core.fama_macbeth import run_fama_macbeth
from opinion_trading.core.sentiment_panel import build_sentiment_panel, measures_for_group
from opinion_trading.core.thesis_models import merge_panel_with_returns, run_thesis_models


def test_antweiler_bullishness_symmetric():
    assert abs(antweiler_bullishness(5, 5)) < 1e-12
    assert antweiler_bullishness(10, 0) > 0
    assert antweiler_bullishness(0, 10) < 0
    assert 0.0 <= antweiler_agreement(8, 2) <= 1.0
    assert antweiler_agreement(0, 0) == 0.0


def test_bullishness_from_rows():
    rows = [
        {"ai_score": 0.8},
        {"ai_score": 0.6},
        {"ai_score": -0.7},
        {"ai_score": 0.0},
    ]
    out = bullishness_from_rows(rows, threshold=0.05)
    assert out["n_bull"] == 2
    assert out["n_bear"] == 1
    assert out["n_neutral"] == 1
    assert out["bullishness"] > 0


def test_measures_for_group_columns():
    rows = [
        {
            "ai_score": 0.5,
            "keyword_score": 0.2,
            "post_time": "2026-03-15 10:00:00",
            "authority_weight": 1.2,
            "event_type": "earnings",
        },
        {
            "ai_score": -0.4,
            "keyword_score": -0.3,
            "post_time": "2026-03-15 12:00:00",
            "authority_weight": 0.9,
            "event_type": "general",
        },
    ]
    m = measures_for_group(rows, date(2026, 3, 15))
    for key in (
        "sent_mean",
        "sent_inf",
        "sent_dict",
        "sent_llm",
        "bullishness",
        "attention_m",
        "sent_x_m",
    ):
        assert key in m


def test_build_sentiment_panel_and_models():
    raw = []
    for d in ("2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13", "2026-03-14"):
        for i, sym in enumerate(("600519.SH", "000001.SZ", "600036.SH", "601318.SH", "000858.SZ")):
            raw.append(
                {
                    "trade_date": d,
                    "symbol": sym,
                    "ai_score": 0.2 * (i - 2),
                    "keyword_score": 0.1 * (i - 2),
                    "post_time": f"{d} 09:30:00",
                    "authority_weight": 1.0,
                    "event_type": "general",
                    "is_noise": False,
                }
            )
            raw.append(
                {
                    "trade_date": d,
                    "symbol": sym,
                    "ai_score": -0.1 * (i - 2),
                    "keyword_score": -0.05 * (i - 2),
                    "post_time": f"{d} 14:00:00",
                    "authority_weight": 1.1,
                    "event_type": "policy",
                    "is_noise": False,
                }
            )
    panel = build_sentiment_panel(raw)
    assert not panel.empty
    assert {"sent_mean", "bullishness", "sent_dict", "sent_llm"}.issubset(panel.columns)

    # Synthetic prices with mild drift correlated to symbol index
    price_rows = []
    for sym_i, sym in enumerate(
        ("600519.SH", "000001.SZ", "600036.SH", "601318.SH", "000858.SZ")
    ):
        px = 100.0 + sym_i
        for d in pd.bdate_range("2026-03-10", periods=10):
            px *= 1.0 + 0.001 * (sym_i - 2) + np.random.default_rng(0).normal(0, 0.001)
            price_rows.append({"date": d, "symbol": sym, "close": px})
    prices = pd.DataFrame(price_rows)
    results = run_thesis_models(panel, prices, horizons=(1, 3))
    assert not results["fama_macbeth"].empty
    assert not results["logit"].empty
    assert set(results["fama_macbeth"]["measure"]) <= set(
        ["sent_mean", "sent_inf", "sent_dict", "sent_llm", "bullishness"]
    )


def test_fama_macbeth_and_logit_smoke():
    rng = np.random.default_rng(42)
    rows = []
    for d in pd.bdate_range("2026-01-01", periods=12):
        for i in range(8):
            s = rng.normal()
            rows.append(
                {
                    "trade_date": d,
                    "symbol": f"S{i}",
                    "sent_mean": s,
                    "ret_1d": 0.01 * s + rng.normal(0, 0.01),
                    "lag_ret_1d": rng.normal(0, 0.01),
                    "attention_m": 1.0,
                }
            )
    df = pd.DataFrame(rows)
    fm = run_fama_macbeth(df, measure_col="sent_mean", horizon=1, min_cross_section=5)
    assert fm.n_days > 0
    assert np.isfinite(fm.coef_mean)
    lg = run_direction_logit(df, measure_col="sent_mean", horizon=1)
    assert lg.n_obs > 0
    assert 0.0 <= lg.accuracy <= 1.0
