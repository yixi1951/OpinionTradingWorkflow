from __future__ import annotations

from opinion_trading.core.ai_sentiment import (
    AISentimentAnalyzer,
    clamp_score,
    sentiment_intensity_label,
)


def test_clamp_score():
    assert clamp_score(2.0) == 1.0
    assert clamp_score(-2.0) == -1.0


def test_sentiment_intensity_label_zh():
    assert "看多" in sentiment_intensity_label(0.4, "zh")
    assert sentiment_intensity_label(0.0, "zh") == "中性"


def test_keyword_analyze_bullish(monkeypatch):
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")
    analyzer = AISentimentAnalyzer()
    # Force openclaw to None so keyword is used
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["利好上涨突破，看多买入加仓龙头"])
    assert len(results) == 1
    assert results[0].source == "keyword"
    assert results[0].score > 0.1
    assert results[0].pos_hits >= 3


def test_keyword_analyze_bearish(monkeypatch):
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")
    analyzer = AISentimentAnalyzer()
    analyzer.openclaw = None
    results = analyzer.analyze_texts(["利空暴跌风险，看空卖出减仓踩雷"])
    assert results[0].score < -0.1
    assert results[0].neg_hits >= 3


def test_score_texts_returns_floats(monkeypatch):
    monkeypatch.delenv("OPENCLAW_URL", raising=False)
    monkeypatch.setenv("ENABLE_TRANSFORMERS_PIPELINE", "0")
    analyzer = AISentimentAnalyzer()
    analyzer.openclaw = None
    scores = analyzer.score_texts(["中性观望"])
    assert len(scores) == 1
    assert -1.0 <= scores[0] <= 1.0