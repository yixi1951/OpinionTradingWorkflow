from __future__ import annotations


import pandas as pd

from opinion_trading.core.ai_sentiment import AISentimentAnalyzer, fuse_scores
from opinion_trading.core.evaluation import evaluate_signals, save_evaluation
from opinion_trading.core.factor_metrics import (
    compute_excess_return,
    compute_factor_ic,
    compute_icir,
)
from opinion_trading.core.semantic_enrichment import (
    classify_event,
    enrich_raw_row,
    match_entities,
    platform_meta,
    semantic_quality_stats,
)


def test_fuse_scores_weights():
    out = fuse_scores(1.0, -1.0, primary_weight=0.7, secondary_weight=0.3)
    assert abs(out - 0.4) < 1e-6


def test_hybrid_blend_without_openclaw(monkeypatch):
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    analyzer = AISentimentAnalyzer(enable_fusion=True)
    results = analyzer.analyze_texts(["强烈看好突破上涨", "暴跌利空风险很大"])
    assert len(results) == 2
    assert results[0].score > results[1].score
    assert results[0].source in {"keyword", "hybrid"}


def test_platform_taxonomy_and_entity_match():
    meta = platform_meta("guba")
    assert meta["type"] == "forum"
    assert "股吧" in meta["label_zh"]
    ok, tokens = match_entities("贵州茅台今天大涨", "600519.SH")
    assert ok
    assert any("茅台" in t or "600519" in t for t in tokens)


def test_event_and_authority_enrichment():
    row = enrich_raw_row(
        {
            "platform": "sina_finance",
            "symbol": "600519.SH",
            "title": "贵州茅台发布年报",
            "content": "业绩超预期，营收增长，据悉机构增持",
            "capture_status": "success",
            "is_noise": False,
        }
    )
    assert row["platform_type"] == "news"
    assert row["entity_matched"] is True
    assert row["event_type"] in {"earnings", "mna", "general"}
    assert row["authority_grade"] in {"high", "medium", "low"}
    assert float(row["authority_weight"]) >= 0.35
    assert classify_event("传闻利好但尚未证实") == "rumor"
    assert classify_event("公司发布年报业绩超预期") == "earnings"


def test_semantic_quality_stats():
    rows = [
        enrich_raw_row(
            {
                "platform": "guba",
                "symbol": "600519.SH",
                "title": "茅台加油",
                "content": "看多",
                "capture_status": "success",
            }
        ),
        enrich_raw_row(
            {
                "platform": "weibo",
                "symbol": "000001.SZ",
                "title": "无关闲聊",
                "content": "今天天气不错打卡",
                "capture_status": "success",
            }
        ),
    ]
    stats = semantic_quality_stats(rows)
    assert 0.0 <= stats["entity_match_rate"] <= 1.0
    assert "comment_share" in stats


def test_factor_ic_and_excess():
    ic = compute_factor_ic([0.9, 0.2, -0.5, 0.1], [0.03, 0.01, -0.02, 0.0])
    assert -1.0 <= ic <= 1.0
    assert compute_icir([0.1, 0.2, 0.05, 0.15]) != 0.0
    excess = compute_excess_return([0.01, 0.02, -0.01], [0.0, 0.01, 0.0])
    assert "excess_return_ann" in excess
    assert "strategy_ann" in excess


def test_evaluate_signals_includes_factor_metrics(tmp_path):
    signal_df = pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "symbol": "600519.SH",
                "action": "BUY",
                "confidence": 0.8,
                "reason": "test",
                "platforms": ["guba"],
            },
            {
                "trade_date": "2026-05-01",
                "symbol": "000001.SZ",
                "action": "SELL",
                "confidence": 0.7,
                "reason": "test",
                "platforms": ["weibo"],
            },
            {
                "trade_date": "2026-05-02",
                "symbol": "600519.SH",
                "action": "BUY",
                "confidence": 0.6,
                "reason": "test",
                "platforms": ["guba"],
            },
        ]
    )
    signal_df["trade_date"] = pd.to_datetime(signal_df["trade_date"])
    price_df = pd.DataFrame(
        [
            {"date": "2026-05-01", "symbol": "600519.SH", "close": 100.0},
            {"date": "2026-05-02", "symbol": "600519.SH", "close": 105.0},
            {"date": "2026-05-03", "symbol": "600519.SH", "close": 104.0},
            {"date": "2026-05-01", "symbol": "000001.SZ", "close": 10.0},
            {"date": "2026-05-02", "symbol": "000001.SZ", "close": 9.5},
            {"date": "2026-05-03", "symbol": "000001.SZ", "close": 9.6},
        ]
    )
    merged, summary = evaluate_signals(signal_df, price_df)
    assert summary.total_signals >= 2
    assert hasattr(summary, "factor_ic")
    assert hasattr(summary, "excess_return_ann")
    assert 0.0 <= summary.signal_coverage <= 1.0
    outputs = save_evaluation(str(tmp_path), merged, summary)
    md = open(outputs["md"], encoding="utf-8").read()
    assert "Factor IC" in md
    assert "Excess return" in md
