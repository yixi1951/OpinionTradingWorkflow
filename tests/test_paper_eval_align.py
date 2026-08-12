"""Paper equity vs evaluate_signals alignment."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def test_paper_equity_uses_price_df(tmp_path: Path) -> None:
    from opinion_trading.core.paper_equity import build_paper_equity_curve

    mem = tmp_path / "memory"
    mem.mkdir()
    line = (
        '{"trade_date":"2026-06-17","symbol":"AAA","action":"BUY",'
        '"shares":10,"price":100.0,"cash_after":99000.0,"note":""}\n'
    )
    (mem / "trade_history.jsonl").write_text(line, encoding="utf-8")
    prices = pd.DataFrame(
        [
            {"date": "2026-06-17", "symbol": "AAA", "close": 110.0},
            {"date": "2026-06-18", "symbol": "AAA", "close": 112.0},
        ]
    )
    df = build_paper_equity_curve(str(mem), price_df=prices, use_market_prices=False)
    assert len(df) == 1
    # 99000 cash + 10*110 mark
    assert float(df.iloc[0]["total_value"]) == 100100.0


def test_align_paper_vs_eval_writes_report(tmp_path: Path) -> None:
    from opinion_trading.core.paper_equity import align_paper_vs_eval

    mem = tmp_path / "memory"
    mem.mkdir()
    reports = tmp_path / "reports"
    reports.mkdir()
    (mem / "trade_history.jsonl").write_text(
        '{"trade_date":"2026-06-17","symbol":"AAA","action":"BUY",'
        '"shares":10,"price":100.0,"cash_after":99000.0,"note":""}\n',
        encoding="utf-8",
    )
    (mem / "signal_history.jsonl").write_text(
        json.dumps(
            {
                "trade_date": "2026-06-17",
                "symbol": "AAA",
                "action": "BUY",
                "confidence": 0.8,
                "reason": "t",
                "platforms": ["guba"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    prices = pd.DataFrame(
        [
            {"date": "2026-06-17", "symbol": "AAA", "close": 100.0},
            {"date": "2026-06-18", "symbol": "AAA", "close": 105.0},
        ]
    )
    result = align_paper_vs_eval(
        str(mem),
        prices,
        str(mem / "signal_history.jsonl"),
        report_dir=str(reports),
    )
    assert result["paper_days"] == 1
    assert result["eval_signals"] >= 1
    assert Path(result["paths"]["md"]).is_file()
    assert Path(result["paths"]["json"]).is_file()
