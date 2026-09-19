"""Tests for engineering-complete slice (semantic dedup, winsorize ext, costs, tz, ML scaffolds)."""

from __future__ import annotations

from datetime import date


from opinion_trading.agents.analyst_base import AnalystOpinion
from opinion_trading.agents.consensus_engine import ConsensusConfig, ConsensusEngine
from opinion_trading.core.batch_scoring import BatchScoringConfig, batch_score_texts
from opinion_trading.core.macro_industry_factors import (
    append_stub_factor_opinions,
    load_macro_industry_factor_config,
    stub_industry_opinion,
)
from opinion_trading.core.models import SentimentWinsorizeConfig
from opinion_trading.core.multi_label_sentiment import (
    enrich_rows_multi_label,
    infer_multi_labels,
    load_multi_label_sentiment_config,
)
from opinion_trading.core.semantic_near_dedup import (
    SemanticNearDedupConfig,
    dedupe_near_semantic,
    jaccard_similarity,
)
from opinion_trading.core.sentiment_winsorize import winsorize_raw_rows
from opinion_trading.core.timezone_utils import normalize_trade_date
from opinion_trading.core.transaction_costs import (
    TransactionCostConfig,
    apply_minimum_commission_bps,
    load_transaction_cost_config,
    resolve_one_way_fee_bps,
)


def test_normalize_trade_date_messy_strings():
    assert normalize_trade_date("2026/06/17") == date(2026, 6, 17)
    assert normalize_trade_date("20260617") == date(2026, 6, 17)
    assert normalize_trade_date("2026-06-17T08:00:00+08:00") == date(2026, 6, 17)


def test_semantic_near_dedup_jaccard():
    cfg = SemanticNearDedupConfig(enabled=True, jaccard_threshold=0.8)
    rows = [
        {"title": "茅台业绩超预期", "content": "继续看多龙头配置价值"},
        {"title": "茅台业绩超预期", "content": "继续看多龙头配置价值啊"},
    ]
    kept, n = dedupe_near_semantic(rows, config=cfg)
    assert n == 1
    assert len(kept) == 1
    assert jaccard_similarity({"abc", "bcd"}, {"abc", "xyz"}) < 1.0


def test_semantic_near_dedup_disabled():
    cfg = SemanticNearDedupConfig(enabled=False)
    rows = [{"title": "a", "content": "b"}, {"title": "a", "content": "b"}]
    kept, n = dedupe_near_semantic(rows, config=cfg)
    assert n == 0 and len(kept) == 2


def test_winsorize_per_symbol():
    cfg = SentimentWinsorizeConfig(
        enabled=True, lower_pct=10, upper_pct=90, per_symbol=True
    )
    rows = [
        {"symbol": "A", "keyword_score": 0.0},
        {"symbol": "A", "keyword_score": 1.0},
        {"symbol": "B", "keyword_score": 0.0},
        {"symbol": "B", "keyword_score": 1.0},
    ]
    out = winsorize_raw_rows(rows, config=cfg)
    scores_a = [r["keyword_score"] for r in out if r["symbol"] == "A"]
    assert min(scores_a) >= 0.0 and max(scores_a) <= 1.0


def test_transaction_cost_min_commission_and_transfer():
    cfg = TransactionCostConfig(
        enabled=True,
        commission_tiers=[],
        stamp_tax_calendar=[],
        min_commission_cny=5.0,
        transfer_fee_bps=0.5,
    )
    bps = resolve_one_way_fee_bps(
        0.0, action="BUY", config=cfg, notional_cny=1000.0
    )
    assert bps >= apply_minimum_commission_bps(0.5, 1000.0, 5.0)
    loaded = load_transaction_cost_config(
        {
            "execution": {
                "transaction_costs": {
                    "enabled": True,
                    "min_commission_cny": 5,
                    "transfer_fee_bps": 1,
                }
            }
        }
    )
    assert loaded.min_commission_cny == 5.0


def test_multi_label_default_off():
    cfg = load_multi_label_sentiment_config({})
    assert cfg.enabled is False
    rows = [{"title": "利好上涨", "content": "买入"}]
    assert enrich_rows_multi_label(rows, config=cfg) == rows


def test_multi_label_tags_when_enabled():
    cfg = load_multi_label_sentiment_config(
        {"scoring": {"multi_label_sentiment": {"enabled": True}}}
    )
    tags = infer_multi_labels("利好上涨突破，但也存在观望分歧")
    assert "bullish" in tags
    out = enrich_rows_multi_label([{"title": "x", "content": "利好上涨"}], config=cfg)
    assert "sentiment_labels" in out[0]


def test_macro_stub_neutral():
    cfg = load_macro_industry_factor_config(
        {
            "analysis": {
                "macro_industry_factors": {
                    "enabled": True,
                    "industry_weight": 0.05,
                    "macro_weight": 0.05,
                }
            }
        }
    )
    op = stub_industry_opinion("600519.SH", date(2026, 6, 17))
    assert op.score == 0.0
    base = [
        AnalystOpinion(
            "600519.SH",
            date(2026, 6, 17),
            "sentiment",
            0.5,
            0.8,
            "",
        ),
        AnalystOpinion(
            "600519.SH",
            date(2026, 6, 17),
            "technical",
            0.3,
            0.7,
            "",
        ),
        AnalystOpinion(
            "600519.SH",
            date(2026, 6, 17),
            "fundamental",
            0.2,
            0.6,
            "",
        ),
    ]
    extended = append_stub_factor_opinions(
        base,
        symbols=["600519.SH"],
        trade_date=date(2026, 6, 17),
        config=cfg,
    )
    assert len(extended) == 5
    engine = ConsensusEngine(ConsensusConfig(min_analysts=2))
    sigs = engine.compute_consensus(extended, date(2026, 6, 17))
    assert sigs


def test_batch_scoring_chunks():
    cfg = BatchScoringConfig(enabled=True, chunk_size=2, mode="keyword")
    texts = ["利好上涨", "暴跌风险", "中性观望", "突破增长"]
    scores, stats = batch_score_texts(texts, config=cfg)
    assert len(scores) == 4
    assert stats["chunks"] == 2


def test_annotation_fixture_72_rows():
    from pathlib import Path

    import pandas as pd

    path = Path("tests/fixtures/annotation_sample_labeled.csv")
    df = pd.read_csv(path)
    assert len(df) == 72
    assert set(df["label"].str.lower()) >= {"bull", "bear", "neutral"}


def test_compare_ml_baseline_smoke():
    from pathlib import Path

    from opinion_trading.core.ml_baseline import compare_tfidf_vs_keyword, load_labeled_csv

    df = load_labeled_csv(str(Path("tests/fixtures/annotation_sample_labeled.csv")))
    report, _ = compare_tfidf_vs_keyword(df, test_size=0.34, seed=42)
    assert report.n_samples >= 40
