from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from text_quality import is_boilerplate, strip_boilerplate


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


def test_is_user_comment_rejects_news_headline() -> None:
    from text_quality import is_user_comment

    assert not is_user_comment("纳斯达克100指数期货转跌，标普500指数期货下跌0.3%")
    assert not is_user_comment("中软国际：正式进军算力业务")
    assert is_user_comment("保险板块分析：看资金明后天会形成金叉，但是主要看的是与科技之间的跷跷板效应")


def test_is_user_comment_rejects_sina_finance() -> None:
    from text_quality import is_user_comment

    assert not is_user_comment("18只白酒股下跌 贵州茅台1307.22元/股收盘", platform="sina_finance")
