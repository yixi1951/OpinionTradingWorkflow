from __future__ import annotations

import json

import pandas as pd

from opinion_trading.core.evaluation import (
    compute_next_returns,
    evaluate_signals,
    load_signals,
    load_prices,
    normalize_price_frame,
    save_evaluation,
)


def test_load_signals_missing_file_returns_empty_df(tmp_path):
    df = load_signals(str(tmp_path / "missing.jsonl"))
    assert df.empty
    assert list(df.columns) == [
        "trade_date",
        "symbol",
        "action",
        "confidence",
        "reason",
        "platforms",
    ]


def test_load_signals_and_prices_and_evaluate(tmp_path):
    signal_path = tmp_path / "signals.jsonl"
    signal_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "trade_date": "2026-05-01",
                        "symbol": "600519.SH",
                        "action": "BUY",
                        "confidence": 0.8,
                        "reason": "test",
                        "platforms": ["guba"],
                    }
                ),
                json.dumps(
                    {
                        "trade_date": "2026-05-02",
                        "symbol": "600519.SH",
                        "action": "SELL",
                        "confidence": 0.7,
                        "reason": "test",
                        "platforms": ["guba"],
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    signal_df = load_signals(str(signal_path))
    assert not signal_df.empty

    price_csv = tmp_path / "prices.csv"
    pd.DataFrame(
        [
            {"date": "2026-05-01", "symbol": "600519.SH", "close": 100.0},
            {"date": "2026-05-02", "symbol": "600519.SH", "close": 110.0},
            {"date": "2026-05-03", "symbol": "600519.SH", "close": 99.0},
        ]
    ).to_csv(price_csv, index=False)

    price_df = load_prices(str(price_csv))
    norm = normalize_price_frame(price_df)
    next_ret = compute_next_returns(norm)
    assert "next_return" in next_ret.columns

    merged, summary = evaluate_signals(signal_df, price_df, "2026-05-01", "2026-05-03")
    assert not merged.empty
    assert summary.total_signals == 2
    assert summary.win_rate >= 0.0

    outputs = save_evaluation(str(tmp_path / "reports"), merged, summary)
    assert outputs["csv"].endswith(".csv")
    assert outputs["md"].endswith(".md")
