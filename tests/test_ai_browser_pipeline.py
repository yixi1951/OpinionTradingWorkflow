"""Tests for browser HTML extract + AI content pipeline (no live network)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch


from opinion_trading.core.ai_content_pipeline import (
    run_ai_content_pipeline,
    score_sentiment,
    screen_relevance,
)
from opinion_trading.integrations.browser_collect import (
    extract_posts_from_html,
    load_platform_cookie,
    _parse_cookie_header,
)


def test_parse_cookie_header():
    cookies = _parse_cookie_header("a=1; b=two; ; =bad", ".xueqiu.com")
    assert {"name": "a", "value": "1", "domain": ".xueqiu.com", "path": "/"} in cookies
    assert any(c["name"] == "b" and c["value"] == "two" for c in cookies)


def test_load_platform_cookie_json(monkeypatch):
    monkeypatch.setenv(
        "PLATFORM_COOKIES_JSON",
        '{"xueqiu":"xq=1","weibo":"wb=2"}',
    )
    assert load_platform_cookie("xueqiu") == "xq=1"
    assert load_platform_cookie("weibo") == "wb=2"


def test_extract_xueqiu_html():
    html = """
    <html><body>
      <article class="timeline__item">贵州茅台业绩超预期，机构上调目标价到2000
        <a href="/status/123">详情</a>
      </article>
      <div>请登录后查看</div>
    </body></html>
    """
    rows = extract_posts_from_html(
        html,
        platform="xueqiu",
        symbol="600519.SH",
        list_url="https://xueqiu.com/S/SH600519",
        trade_date=date(2026, 7, 22),
        max_posts=10,
    )
    assert len(rows) >= 1
    assert rows[0]["capture_status"] == "success"
    assert "茅台" in rows[0]["content"] or "茅台" in rows[0]["title"]
    assert rows[0]["score_source"] == "pending_ai"


def test_extract_weibo_html():
    html = """
    <html><body>
      <div class="card-wrap"><p class="txt">看空白酒板块短期回调，茅台也难独善其身</p></div>
    </body></html>
    """
    rows = extract_posts_from_html(
        html,
        platform="weibo",
        symbol="600519.SH",
        list_url="https://s.weibo.com/weibo?q=600519.SH",
        trade_date=date(2026, 7, 22),
    )
    assert rows
    assert rows[0]["platform"] == "weibo"


def test_screen_relevance_heuristic_ads(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    rows = [
        {
            "symbol": "600519.SH",
            "title": "加微信免费荐股",
            "content": "稳赚不赔扫码进群",
        },
        {
            "symbol": "600519.SH",
            "title": "茅台财报",
            "content": "贵州茅台业绩超预期大涨",
        },
    ]
    out = screen_relevance(rows, enabled=True)
    assert out[0]["ai_relevant"] is False
    assert out[0]["is_noise"] is True
    assert out[1]["ai_relevant"] is True


def test_score_sentiment_uses_analyzer(monkeypatch):
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("SCORING_MODE", "ai")

    fake = MagicMock()
    fake.score = 0.66
    fake.source = "openclaw"

    with patch(
        "opinion_trading.core.ai_sentiment.AISentimentAnalyzer"
    ) as cls:
        inst = cls.return_value
        inst.analyze_texts.return_value = [fake]
        rows = [
            {
                "symbol": "600519.SH",
                "title": "业绩超预期",
                "content": "机构看多",
                "ai_relevant": True,
                "capture_status": "success",
            }
        ]
        out = score_sentiment(rows, enabled=True)
        assert out[0]["ai_score"] == 0.66
        assert out[0]["score_source"] == "openclaw"


def test_run_ai_pipeline_stats(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")

    with patch(
        "opinion_trading.core.ai_sentiment.AISentimentAnalyzer"
    ) as cls:
        inst = cls.return_value
        r = MagicMock()
        r.score = 0.2
        r.source = "keyword"
        inst.analyze_texts.return_value = [r]
        result = run_ai_content_pipeline(
            [
                {
                    "symbol": "600519.SH",
                    "title": "正常讨论行情",
                    "content": "贵州茅台放量上涨",
                    "capture_status": "success",
                }
            ],
            screen_enabled=True,
            score_enabled=True,
        )
    assert "stats" in result
    assert result["stats"]["total"] == 1
    assert len(result["rows"]) == 1


def test_config_loads_ai_browser_flags():
    from opinion_trading.core.config_loader import load_runtime_config

    cfg = load_runtime_config("config/settings.yaml")
    assert cfg.scoring_mode in {"ai", "hybrid", "keyword"}
    assert hasattr(cfg, "browser_enabled")
    assert hasattr(cfg, "ai_screen_enabled")
    assert cfg.ai_batch_size >= 1
