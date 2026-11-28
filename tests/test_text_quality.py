from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from text_quality import (
    is_boilerplate,
    is_low_value_opinion,
    is_precise_opinion,
    is_spam_or_promo,
    quality_issues,
    strip_boilerplate,
)


def test_strip_boilerplate_removes_eastmoney_footer() -> None:
    raw = "今天加仓2.5万股，总持仓45万股 " "东方财富 扫一扫下载APP 东方财富产品 版权所有:东方财富网"
    cleaned = strip_boilerplate(raw)
    assert cleaned == "今天加仓2.5万股，总持仓45万股"
    assert not is_boilerplate(cleaned)


def test_strip_boilerplate_removes_guba_breadcrumb() -> None:
    raw = (
        "股吧首页 > 贵州茅台吧 > 帖子正文 返回贵州茅台吧 > "
        "生活与网的区别 2026-05-27 11:49:39 来自浙江 "
        "时间过去了 6年之后再回首，发现热闹过后，白酒行业的股票只剩下一地"
    )
    cleaned = strip_boilerplate(raw)
    assert "东方财富" not in cleaned
    assert "股吧首页" not in cleaned
    assert "6年之后再回首" in cleaned


def test_strip_boilerplate_empty_for_pure_chrome() -> None:
    raw = "东方财富 扫一扫下载APP 东方财富产品 天天基金 扫一扫下载APP"
    assert strip_boilerplate(raw) == ""


def test_reject_short_fluff() -> None:
    assert is_low_value_opinion("顶")
    assert is_low_value_opinion("周末愉快")
    assert is_low_value_opinion("茅台牛逼")
    assert is_low_value_opinion("哈哈哈哈")
    assert "low_value" in quality_issues("路过")


def test_reject_spam_promo() -> None:
    assert is_spam_or_promo("加微信abc123稳赚不赔")
    assert is_spam_or_promo("老师带单进QQ群")
    assert not is_precise_opinion("加V私信领免费指标荐股")


def test_reject_news_headline() -> None:
    headline = "贵州茅台公告：公司拟回购股份不超过10亿元"
    assert not is_precise_opinion(headline, platform="guba")
    assert "news_headline" in quality_issues(headline, platform="guba")


def test_keep_real_retail_opinion() -> None:
    text = "今天继续加仓茅台，估值虽然不便宜但中长期还是看好持有"
    assert is_precise_opinion(text, platform="guba", title=text)
    assert quality_issues(text, title=text, platform="guba") == []
