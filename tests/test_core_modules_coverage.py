"""High-value unit tests for core modules (no network / no Streamlit)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from opinion_trading.agents.analyst_base import AnalystOpinion
from opinion_trading.agents.consensus_engine import ConsensusConfig, ConsensusEngine
from opinion_trading.agents.fundamental_analyst import FundamentalAnalyst
from opinion_trading.agents.technical_analyst import TechnicalAnalyst
from opinion_trading.core.data_quality import (
    apply_quality_to_sentiment_confidence,
    evaluate_raw_quality,
)
from opinion_trading.core.fundamentals import analyst_score as fund_score
from opinion_trading.core.market_data import (
    fetch_close_on_date,
    set_local_price_table,
)
from opinion_trading.core.technical_indicators import (
    add_rsi,
    analyst_score as tech_score,
    compute_all_indicators,
)
from opinion_trading.core.text_dedup import content_fingerprint, dedupe_raw_rows


def _ohlcv(n: int = 40) -> pd.DataFrame:
    idx = pd.date_range("2026-04-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 120, n), index=idx)
    high = close + 1.5
    low = close - 1.2
    open_ = close.shift(1).fillna(close.iloc[0])
    volume = pd.Series(1_000_000 + np.arange(n) * 1000, index=idx)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}
    )


def test_technical_indicators_and_scores():
    df = compute_all_indicators(_ohlcv())
    assert "RSI" in df.columns
    assert "MACD" in df.columns
    scores = tech_score(df)
    assert -1.0 <= scores["score"] <= 1.0
    empty = add_rsi(pd.DataFrame())
    assert empty.empty


def test_fundamentals_score_value_and_growth():
    cheap = fund_score(
        {
            "pe": 8.0,
            "roe": 0.22,
            "revenue_growth": 0.20,
            "market_cap": 2e12,
            "beta": 1.0,
            "profit_margins": 0.25,
        }
    )
    expensive = fund_score(
        {
            "pe": 80.0,
            "roe": 0.02,
            "revenue_growth": -0.1,
            "market_cap": 5e8,
            "beta": 2.5,
            "profit_margins": -0.05,
        }
    )
    assert cheap["score"] > expensive["score"]


def test_consensus_neutral_and_min_analysts():
    engine = ConsensusEngine(ConsensusConfig(min_analysts=2, min_confidence=0.9))
    td = date(2026, 6, 1)
    weak = [
        AnalystOpinion("600519.SH", td, "sentiment", 0.05, 0.2, "s"),
        AnalystOpinion("600519.SH", td, "technical", 0.04, 0.2, "t"),
    ]
    out = engine.compute_consensus(weak, td)
    assert len(out) == 1
    assert out[0].consensus_direction == "NEUTRAL"

    lonely = [AnalystOpinion("000001.SZ", td, "sentiment", 0.8, 0.9, "only")]
    assert engine.compute_consensus(lonely, td) == []


def test_consensus_require_sentiment():
    engine = ConsensusEngine(ConsensusConfig(require_sentiment=True, min_analysts=2))
    td = date(2026, 6, 1)
    ops = [
        AnalystOpinion("600519.SH", td, "technical", 0.5, 0.8, "t"),
        AnalystOpinion("600519.SH", td, "fundamental", 0.4, 0.7, "f"),
    ]
    assert engine.compute_consensus(ops, td) == []


def test_technical_analyst_mocked_ohlcv():
    analyst = TechnicalAnalyst(lookback_days=60, min_history_days=20)
    df = _ohlcv(80)
    with patch(
        "opinion_trading.agents.technical_analyst.fetch_ohlcv", return_value=df
    ):
        op = analyst.analyze("600519.SH", date(2026, 6, 17))
    assert op is not None
    assert op.analyst_name == "technical"
    assert op.reasoning


def test_fundamental_analyst_mocked_fetch():
    analyst = FundamentalAnalyst()
    with patch(
        "opinion_trading.agents.fundamental_analyst.fetch_fundamentals",
        return_value={"pe": 12.0, "roe": 0.18, "revenue_growth": 0.1, "name": "x"},
    ):
        op = analyst.analyze("600519.SH", date(2026, 6, 17))
    assert op is not None
    assert op.analyst_name == "fundamental"
    assert "PE" in op.reasoning


def test_quality_and_dedup_keep_last():
    rows = [
        {
            "platform": "guba",
            "symbol": "600519.SH",
            "title": "A",
            "content": "duplicate body text here",
            "capture_status": "success",
        },
        {
            "platform": "guba",
            "symbol": "600519.SH",
            "title": "A",
            "content": "duplicate body text here",
            "capture_status": "success",
        },
    ]
    assert content_fingerprint(rows[0]) == content_fingerprint(rows[1])
    out, n = dedupe_raw_rows(rows, keep="last")
    assert n == 1
    assert len(out) == 1

    noisy = [
        {
            "platform": "guba",
            "title": "短",
            "content": "x",
            "post_time": "",
            "capture_status": "fallback",
            "failure_reason": "timeout",
        }
        for _ in range(8)
    ]
    gate = evaluate_raw_quality(noisy, max_noise_rate=0.05)
    scaled = apply_quality_to_sentiment_confidence(0.8, gate)
    assert scaled < 0.8
    assert apply_quality_to_sentiment_confidence(0.8, None) == 0.8


def test_market_data_prefers_local_table_over_network():
    table = pd.DataFrame(
        [{"date": "2026-06-17", "symbol": "600519.SH", "close": 1234.5}]
    )
    set_local_price_table(table)
    with patch("opinion_trading.core.market_data.fetch_ohlcv") as mocked:
        px, src = fetch_close_on_date("600519.SH", date(2026, 6, 17))
        mocked.assert_not_called()
    assert src == "price_table"
    assert px == pytest.approx(1234.5)
    set_local_price_table(None)
