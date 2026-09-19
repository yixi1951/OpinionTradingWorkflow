from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from opinion_trading.core.evaluation import (
    evaluate_signals,
    load_prices,
    lookup_close,
    resolve_price_csv,
)
from opinion_trading.core.market_data import (
    fetch_close_on_date,
    set_local_price_table,
)
from opinion_trading.core.paper_equity import (
    build_paper_equity_curve,
    validate_paper_eval_price_alignment,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def replay_prices():
    return load_prices(str(FIXTURES / "price_history_replay.csv"))


def test_lookup_close_matches_fixture_row(replay_prices):
    px = lookup_close(replay_prices, "600519.SH", date(2026, 6, 17))
    row = replay_prices[
        (replay_prices["symbol"] == "600519.SH")
        & (replay_prices["date"] == pd.Timestamp("2026-06-17"))
    ]
    assert px == pytest.approx(float(row.iloc[0]["close"]))


def test_fetch_close_on_date_uses_eval_table(replay_prices):
    set_local_price_table(replay_prices)
    eval_px = lookup_close(replay_prices, "000001.SZ", "2026-06-16")
    paper_px, src = fetch_close_on_date("000001.SZ", date(2026, 6, 16))
    assert src == "price_table"
    assert paper_px == pytest.approx(eval_px)
    set_local_price_table(None)


def test_paper_equity_and_evaluate_signals_share_closes(tmp_path, replay_prices):
    set_local_price_table(replay_prices)
    mem = tmp_path / "memory"
    mem.mkdir()
    eval_close = lookup_close(replay_prices, "600519.SH", date(2026, 6, 17))
    assert eval_close is not None
    line = json.dumps(
        {
            "trade_date": "2026-06-17",
            "symbol": "600519.SH",
            "action": "BUY",
            "shares": 10,
            "price": float(eval_close),
            "cash_after": 100000.0 - 10 * float(eval_close),
            "note": "[price=x src=price_table]",
        }
    )
    (mem / "trade_history.jsonl").write_text(line + "\n", encoding="utf-8")
    (mem / "signal_history.jsonl").write_text(
        json.dumps(
            {
                "trade_date": "2026-06-17",
                "symbol": "600519.SH",
                "action": "BUY",
                "confidence": 0.8,
                "reason": "align",
                "platforms": ["guba"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    eq = build_paper_equity_curve(
        str(mem), use_market_prices=True, price_df=replay_prices
    )
    assert len(eq) == 1
    expected_pos = 10 * float(eval_close)
    assert float(eq.iloc[0]["position_value"]) == pytest.approx(expected_pos, rel=1e-6)

    sig = pd.read_json(mem / "signal_history.jsonl", lines=True)
    sig["trade_date"] = pd.to_datetime(sig["trade_date"])
    merged, summary = evaluate_signals(sig, replay_prices)
    assert summary.total_signals >= 1
    merged_close = float(merged.iloc[0]["close"])
    assert merged_close == pytest.approx(float(eval_close))

    report = validate_paper_eval_price_alignment(replay_prices, str(mem))
    assert report["compared"] >= 1
    assert report["aligned"] is True
    assert report["mismatch_count"] == 0
    set_local_price_table(None)


def test_alignment_detects_paper_lookup_mismatch(tmp_path, replay_prices, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "signal_history.jsonl").write_text(
        json.dumps(
            {
                "trade_date": "2026-06-17",
                "symbol": "600519.SH",
                "action": "BUY",
                "confidence": 0.8,
                "reason": "x",
                "platforms": ["guba"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_close(symbol, trade_date):
        return 9999.0, "synthetic"

    monkeypatch.setattr(
        "opinion_trading.core.market_data.fetch_close_on_date", fake_close
    )
    report = validate_paper_eval_price_alignment(replay_prices, str(mem))
    assert report["aligned"] is False
    assert report["mismatch_count"] >= 1


def test_resolve_price_csv_prefers_existing_fixture():
    path = resolve_price_csv(str(FIXTURES / "price_history_replay.csv"))
    assert Path(path).is_file()
    assert path.endswith("price_history_replay.csv")
