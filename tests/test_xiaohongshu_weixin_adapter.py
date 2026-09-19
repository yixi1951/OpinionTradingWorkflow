from __future__ import annotations

from datetime import date
from pathlib import Path
import unittest

from opinion_trading.integrations.platform_sentiment_real import (
    RealPlatformSentimentProvider,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class XiaohongshuAdapterTests(unittest.TestCase):
    def test_build_url_xiaohongshu(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        url = provider._build_url("xiaohongshu", "600519.SH")
        self.assertIn("xiaohongshu.com", url)
        self.assertIn("600519", url)
        alias = provider._build_url("xhs", "600519.SH")
        self.assertIn("xiaohongshu.com", alias)

    def test_collect_xiaohongshu_html_fixture(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        provider.ai_analyzer = None
        html = (FIXTURES / "xiaohongshu_page.html").read_text(encoding="utf-8")
        provider._download_html = lambda url: html  # type: ignore[method-assign]
        rows = provider.collect_raw_posts(
            "xiaohongshu", "600519.SH", date(2026, 6, 17), max_posts=2
        )
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["platform"], "xiaohongshu")
        self.assertEqual(rows[0]["capture_status"], "success")
        self.assertIn("茅台", rows[0]["title"] + rows[0]["content"])
        self.assertIn("xiaohongshu.com", rows[0]["source_page"])

    def test_fetch_xiaohongshu_positive_sample(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        provider.ai_analyzer = None
        html = (FIXTURES / "xiaohongshu_page.html").read_text(encoding="utf-8")
        provider._download_html = lambda url: html  # type: ignore[method-assign]
        result = provider.fetch("xiaohongshu", "600519.SH", date(2026, 6, 17))
        self.assertGreater(result["sentiment_score"], 0.0)
        self.assertGreaterEqual(int(result["post_count"]), 1)


class WeixinAdapterTests(unittest.TestCase):
    def test_build_url_weixin(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        url = provider._build_url("weixin", "600519.SH")
        self.assertTrue("sogou.com" in url or "weixin" in url)
        self.assertIn("600519", url)
        alias = provider._build_url("gongzhonghao", "600519.SH")
        self.assertIn("600519", alias)

    def test_collect_weixin_html_fixture(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        provider.ai_analyzer = None
        html = (FIXTURES / "weixin_page.html").read_text(encoding="utf-8")
        provider._download_html = lambda url: html  # type: ignore[method-assign]
        rows = provider.collect_raw_posts(
            "weixin", "600519.SH", date(2026, 6, 17), max_posts=2
        )
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["platform"], "weixin")
        self.assertEqual(rows[0]["capture_status"], "success")
        self.assertIn("茅台", rows[0]["title"] + rows[0]["content"])

    def test_weixin_stub_fallback_when_download_fails(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=True)
        provider.ai_analyzer = None

        def boom(url: str) -> str:
            raise ConnectionError("blocked")

        provider._download_html = boom  # type: ignore[method-assign]
        rows = provider.collect_raw_posts(
            "weixin", "600519.SH", date(2026, 6, 17), max_posts=1
        )
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["capture_status"], "fallback")
