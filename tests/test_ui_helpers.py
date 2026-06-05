from __future__ import annotations

import pandas as pd

from opinion_trading.ui_helpers import (
    build_pick_contribution,
    build_pick_narrative,
    filter_usable_raw,
    parse_platform_scores,
)


def test_parse_platform_scores():
    raw = "guba:0.000, sina_finance:0.300, weibo:-0.100"
    assert parse_platform_scores(raw)["sina_finance"] == 0.3


def test_filter_usable_raw_drops_fallback():
    df = pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "platform": "weibo",
                "title": "600519.SH weibo fallback record",
                "summary": "Fallback row generated",
                "content": "Fallback row generated",
                "capture_status": "fallback",
                "is_noise": True,
                "ai_score": 0.0,
            },
            {
                "symbol": "600519.SH",
                "platform": "sina_finance",
                "title": "18只白酒股下跌 贵州茅台1307.22元/股收盘",
                "summary": "(06-02) 18只白酒股下跌",
                "content": "(06-02) 18只白酒股下跌",
                "capture_status": "success",
                "is_noise": False,
                "ai_score": -0.28,
            },
        ]
    )
    usable = filter_usable_raw(df)
    assert len(usable) == 1
    assert usable.iloc[0]["platform"] == "sina_finance"


def test_build_pick_contribution_uses_realtime_scores():
    picks = pd.DataFrame(
        [
            {
                "symbol": "601318.SH",
                "avg_score": 0.036,
                "platform_scores": "sina_finance:0.300, weibo:-0.100",
            }
        ]
    )
    contrib = build_pick_contribution(
        "601318.SH", picks, pd.DataFrame(), pd.DataFrame()
    )
    assert not contrib.empty
    sina = contrib[contrib["platform"] == "sina_finance"].iloc[0]
    assert sina["platform_score"] == 0.3
    assert sina["weight_pct"] > 0


def test_build_pick_narrative_zh():
    picks = pd.DataFrame(
        [{"symbol": "X", "avg_score": 0.03, "platform_scores": "sina_finance:0.3"}]
    )
    raw = pd.DataFrame(
        [
            {
                "symbol": "X",
                "platform": "sina_finance",
                "title": "业绩超预期",
                "summary": "业绩超预期",
                "content": "业绩超预期",
                "capture_status": "success",
                "is_noise": False,
                "ai_score": 0.5,
            }
        ]
    )
    contrib = build_pick_contribution("X", picks, raw, pd.DataFrame())
    text = build_pick_narrative("X", 0.03, contrib, raw, lang="zh")
    assert "X" in text
    assert "sina_finance" in text
