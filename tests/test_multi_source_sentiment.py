from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from opinion_trading.core.models import AggregatedSentiment  # noqa: E402
from opinion_trading.integrations.platform_sentiment_real import RealPlatformSentimentProvider  # noqa: E402
from opinion_trading.skills.sentiment_analysis import SentimentAnalysisSkill  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class MultiSourceSentimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trade_date = date(2026, 5, 28)

    def _provider_with_html(self, mapping: dict[str, str]) -> RealPlatformSentimentProvider:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        provider.ai_analyzer = None

        def fake_download_html(url: str) -> str:
            if "list,sh600519.html" in url or "list,600519.html" in url:
                return mapping["eastmoney_list"]
            if "xueqiu.com" in url:
                return mapping["xueqiu_page"]
            if url.endswith("123456789.html") or url.endswith("987654321.html"):
                return mapping["eastmoney_article"]
            raise AssertionError(f"Unexpected url: {url}")

        provider._download_html = fake_download_html  # type: ignore[attr-defined]
        return provider

    def test_build_url_supports_additional_sources(self) -> None:
        provider = RealPlatformSentimentProvider(fallback_to_stub=False)
        self.assertIn("guba.eastmoney.com", provider._build_url("eastmoney", "600519.SH"))
        self.assertIn("xueqiu.com", provider._build_url("xueqiu", "600519.SH"))

    def test_collect_eastmoney_and_xueqiu_samples(self) -> None:
        mapping = {
            "eastmoney_list": (FIXTURES / "eastmoney_list.html").read_text(encoding="utf-8"),
            "eastmoney_article": (FIXTURES / "eastmoney_article.html").read_text(encoding="utf-8"),
            "xueqiu_page": (FIXTURES / "xueqiu_page.html").read_text(encoding="utf-8"),
        }
        provider = self._provider_with_html(mapping)

        eastmoney_rows = provider.collect_raw_posts("eastmoney", "600519.SH", self.trade_date, max_posts=2)
        self.assertGreaterEqual(len(eastmoney_rows), 1)
        self.assertEqual(eastmoney_rows[0]["platform"], "eastmoney")
        self.assertEqual(eastmoney_rows[0]["capture_status"], "success")
        self.assertIn("贵州茅台", eastmoney_rows[0]["title"])

        xueqiu_rows = provider.collect_raw_posts("xueqiu", "600519.SH", self.trade_date, max_posts=2)
        self.assertGreaterEqual(len(xueqiu_rows), 1)
        self.assertEqual(xueqiu_rows[0]["platform"], "xueqiu")
        self.assertEqual(xueqiu_rows[0]["capture_status"], "success")
        self.assertIn("xueqiu.com", xueqiu_rows[0]["source_page"])

    def test_fetch_scores_are_positive_for_positive_samples(self) -> None:
        mapping = {
            "eastmoney_list": (FIXTURES / "eastmoney_list.html").read_text(encoding="utf-8"),
            "eastmoney_article": (FIXTURES / "eastmoney_article.html").read_text(encoding="utf-8"),
            "xueqiu_page": (FIXTURES / "xueqiu_page.html").read_text(encoding="utf-8"),
        }
        provider = self._provider_with_html(mapping)

        eastmoney_result = provider.fetch("eastmoney", "600519.SH", self.trade_date)
        xueqiu_result = provider.fetch("xueqiu", "600519.SH", self.trade_date)

        self.assertGreater(eastmoney_result["sentiment_score"], 0.0)
        self.assertGreater(xueqiu_result["sentiment_score"], 0.0)
        self.assertGreater(eastmoney_result["sentiment_score"], 0.0)
        self.assertGreater(xueqiu_result["sentiment_score"], 0.0)
        self.assertTrue(str(eastmoney_result["source"]).startswith("https://guba.eastmoney.com"))
        self.assertTrue(str(xueqiu_result["source"]).startswith("https://xueqiu.com"))

    def test_weighted_aggregation_uses_configured_weights(self) -> None:
        agg = AggregatedSentiment(
            trade_date=self.trade_date,
            symbol="600519.SH",
            platform_scores={"eastmoney": 0.6, "weibo": -0.2},
            platform_weights={"eastmoney": 2.0, "weibo": 1.0},
        )
        self.assertAlmostEqual(agg.average_score, 0.3333333333, places=6)

        analyzer = SentimentAnalysisSkill(
            bearish_threshold=-0.6,
            bullish_threshold=0.7,
            min_platforms_for_signal=2,
            reversal_min_delta=0.1,
            platform_weights={"eastmoney": 2.0, "weibo": 1.0},
        )
        score = analyzer._combo_quality_score(
            self.trade_date,
            {self.trade_date: {"600519.SH": agg}},
            ["eastmoney", "weibo"],
        )
        self.assertIsInstance(score, float)
        self.assertGreater(score, -1.0)
        self.assertLess(score, 1.0)


if __name__ == "__main__":
    unittest.main()
