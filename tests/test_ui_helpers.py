from __future__ import annotations

import pandas as pd

from opinion_trading.ui_helpers import (
    build_pick_contribution,
    build_pick_narrative,
    build_picks_detail_table,
    filter_comment_evidence,
    filter_usable_raw,
    parse_platform_scores,
    platform_label,
    symbol_display,
    top_comment_rows,
)


def test_parse_platform_scores():
    raw = "guba:0.000, sina_finance:0.300, weibo:-0.100"
    assert parse_platform_scores(raw)["sina_finance"] == 0.3


def test_platform_label_zh():
    assert platform_label("sina_finance", "zh") == "新浪财经"
    assert platform_label("unknown", "zh") == "unknown"


def test_symbol_display_zh():
    assert symbol_display("600519.SH", "zh") == "600519 贵州茅台"
    assert symbol_display("999999.SH", "zh") == "999999.SH"


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
                "platform": "guba",
                "title": "今天继续加仓，长期看好",
                "summary": "今天继续加仓，长期看好",
                "content": "今天继续加仓，长期看好",
                "capture_status": "success",
                "is_noise": False,
                "ai_score": 0.28,
            },
        ]
    )
    usable = filter_usable_raw(df)
    assert len(usable) == 1
    assert usable.iloc[0]["platform"] == "guba"


def test_filter_comment_evidence_drops_news():
    df = pd.DataFrame(
        [
            {
                "symbol": "601318.SH",
                "platform": "weibo",
                "title": "纳斯达克100指数期货转跌，标普500指数期货下跌0.3%",
                "summary": "",
                "content": "",
                "capture_status": "success",
                "is_noise": False,
                "ai_score": -0.29,
            },
            {
                "symbol": "601318.SH",
                "platform": "guba",
                "title": "保险板块分析：看资金明后天会形成金叉",
                "summary": "",
                "content": "保险板块分析：看资金明后天会形成金叉",
                "capture_status": "success",
                "is_noise": False,
                "ai_score": 0.17,
            },
        ]
    )
    comments = filter_comment_evidence(df)
    assert len(comments) == 1
    assert comments.iloc[0]["platform"] == "guba"


def test_top_comment_rows_includes_reference():
    df = pd.DataFrame(
        [
            {
                "symbol": "601318.SH",
                "platform": "guba",
                "title": "长期看好保险龙头",
                "summary": "",
                "content": "长期看好保险龙头，准备加仓",
                "capture_status": "success",
                "is_noise": False,
                "ai_score": 0.25,
            },
            {
                "symbol": "601318.SH",
                "platform": "sina_finance",
                "title": "中国平安发布年报摘要",
                "summary": "",
                "content": "中国平安发布年报摘要",
                "capture_status": "success",
                "is_noise": False,
                "ai_score": 0.1,
            },
        ]
    )
    rows = top_comment_rows(df, "601318.SH", top_n=5, include_reference=True)
    assert "reference" in rows
    assert not rows["positive"].empty or not rows["reference"].empty


def test_build_picks_detail_table_zh():
    picks = pd.DataFrame(
        [
            {
                "symbol": "601318.SH",
                "avg_score": 0.0719,
                "platform_scores": "sina_finance:0.600, weibo:-0.200",
            }
        ]
    )
    table = build_picks_detail_table(picks, lang="zh")
    assert "股票" in table.columns
    assert "新浪财经" in table["平台"].tolist()
    assert "601318 中国平安" in table["股票"].iloc[0]


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
                "platform": "guba",
                "title": "业绩超预期，继续看好",
                "summary": "业绩超预期，继续看好",
                "content": "业绩超预期，继续看好",
                "capture_status": "success",
                "is_noise": False,
                "ai_score": 0.5,
            }
        ]
    )
    contrib = build_pick_contribution("X", picks, raw, pd.DataFrame())
    text = build_pick_narrative("X", 0.03, contrib, raw, lang="zh")
    assert "X" in text
    assert "新浪财经" in text


def test_full_comment_text_keeps_long_body():
    long_body = "看多" + ("，业绩超预期" * 40)
    df = pd.DataFrame(
        [
            {
                "symbol": "600519.SH",
                "platform": "guba",
                "title": "",
                "summary": "",
                "content": long_body,
                "capture_status": "success",
                "is_noise": False,
                "ai_score": 0.4,
            }
        ]
    )
    from opinion_trading.ui_helpers import clean_comment_text, full_comment_text

    full = full_comment_text(df.iloc[0])
    preview = clean_comment_text(df.iloc[0])
    assert len(full) > 220
    assert preview.endswith("…")
    assert full.startswith(preview[:217])
