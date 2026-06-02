from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from text_quality import is_boilerplate, strip_boilerplate


def test_strip_boilerplate_removes_eastmoney_footer() -> None:
    raw = (
        "今天加仓2.5万股，总持仓45万股 "
        "东方财富 扫一扫下载APP 东方财富产品 版权所有:东方财富网"
    )
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
