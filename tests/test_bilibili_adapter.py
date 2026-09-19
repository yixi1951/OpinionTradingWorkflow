from __future__ import annotations

from datetime import date
from pathlib import Path
import unittest

from opinion_trading.integrations.platform_sentiment_real import (
    RealPlatformSentimentProvider,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class BilibiliAdapterTests(unittest.TestCase):
    def test_build_url_bilibili(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        url = provider._build_url("bilibili", "600519.SH")
        self.assertIn("bilibili.com", url)
        self.assertIn("600519", url)

    def test_collect_bilibili_html_fixture(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        provider.ai_analyzer = None
        html = (FIXTURES / "bilibili_page.html").read_text(encoding="utf-8")
        provider._download_html = lambda url: html  # type: ignore[method-assign]
        rows = provider.collect_raw_posts(
            "bilibili", "600519.SH", date(2026, 6, 17), max_posts=2
        )
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["platform"], "bilibili")
        self.assertEqual(rows[0]["capture_status"], "success")
        self.assertIn("茅台", rows[0]["title"] + rows[0]["content"])
        self.assertIn("bilibili.com", rows[0]["source_page"])

    def test_fetch_bilibili_positive_sample(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        provider.ai_analyzer = None
        html = (FIXTURES / "bilibili_page.html").read_text(encoding="utf-8")
        provider._download_html = lambda url: html  # type: ignore[method-assign]
        result = provider.fetch("bilibili", "600519.SH", date(2026, 6, 17))
        self.assertGreater(result["sentiment_score"], 0.0)
        self.assertGreaterEqual(int(result["post_count"]), 1)
