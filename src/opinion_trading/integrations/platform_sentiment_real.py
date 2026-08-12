from __future__ import annotations

import hashlib
import os
import random
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from opinion_trading.core.log_utils import get_logger
from opinion_trading.integrations.platform_sentiment_stub import (
    PlatformSentimentProvider as StubProvider,
)
from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

import sys
from pathlib import Path as _Path

logger = get_logger(__name__)

_scripts_dir = _Path(__file__).resolve().parents[3] / "scripts"
if _scripts_dir.exists() and str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))
try:
    from text_quality import is_boilerplate, strip_boilerplate
except ImportError:

    def is_boilerplate(text: str) -> bool:  # type: ignore[misc]
        return False

    def strip_boilerplate(text: str, *, max_len: int = 800) -> str:  # type: ignore[misc]
        return str(text or "")[:max_len]


# ── HTML 磁盘缓存 ──────────────────────────────────────────────────────────
_HTML_CACHE_DIR: Path | None = None
_LAST_REQUEST_TIME: Dict[str, float] = {}


def _get_cache_dir() -> Path:
    global _HTML_CACHE_DIR
    cache_path = os.environ.get("HTML_CACHE_DIR", "data/html_cache")
    path = Path(cache_path)
    if _HTML_CACHE_DIR is None or _HTML_CACHE_DIR.resolve() != path.resolve():
        _HTML_CACHE_DIR = path
        _HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _HTML_CACHE_DIR


def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _read_html_cache(url: str) -> str | None:
    """Return cached HTML if fresh (within TTL), else None."""
    ttl = int(os.environ.get("HTML_CACHE_TTL_SECONDS", "3600"))
    if ttl <= 0:
        return None
    cache_dir = _get_cache_dir()
    key = _cache_key(url)
    cache_file = cache_dir / key
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < ttl:
            logger.debug("Cache HIT  %s", url[:120])
            return cache_file.read_text(encoding="utf-8")
        cache_file.unlink(missing_ok=True)
    logger.debug("Cache MISS %s", url[:120])
    return None


def _write_html_cache(url: str, html: str) -> None:
    cache_dir = _get_cache_dir()
    key = _cache_key(url)
    cache_file = cache_dir / key
    # Drop lone surrogates from broken page encodings so cache write never aborts collect.
    safe = html.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="ignore")
    cache_file.write_text(safe, encoding="utf-8")


# ── 请求频率控制 ───────────────────────────────────────────────────────────
def _rate_limit(url: str) -> None:
    """Per-domain delay to avoid being blocked."""
    domain = urlparse(url).netloc or "unknown"
    now = time.time()
    last = _LAST_REQUEST_TIME.get(domain, 0.0)
    elapsed = now - last
    min_interval = float(os.environ.get("REQUEST_MIN_INTERVAL", "1.5"))
    if elapsed < min_interval:
        delay = min_interval - elapsed + random.uniform(0, 1.0)
        logger.debug("Rate-limit sleep %.2fs for %s", delay, domain)
        time.sleep(delay)
    _LAST_REQUEST_TIME[domain] = time.time()


# ── 平台名称常量 ────────────────────────────────────────────────────────────
_PLATFORM_GUBA = "guba"
_PLATFORM_EASTMONEY = "eastmoney"
_PLATFORM_SINA = "sina_finance"
_PLATFORM_DOUYIN = "douyin"
_PLATFORM_WEIBO = "weibo"
_PLATFORM_XUEQIU = "xueqiu"


class RealPlatformSentimentProvider:
    """Fetches text from real platform pages and derives a simple sentiment score."""

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    _POSITIVE_WORDS = ["上涨", "利好", "突破", "增长", "看多", "反弹", "盈利", "强势", "买入", "乐观"]
    _NEGATIVE_WORDS = ["下跌", "利空", "风险", "暴跌", "看空", "回撤", "亏损", "弱势", "卖出", "悲观"]

    def __init__(
        self,
        timeout: int = 10,
        fallback_to_stub: bool = True,
        scoring_mode: str | None = None,
        row_level_llm: bool | None = None,
        max_posts: int | None = None,
    ) -> None:
        self.timeout = timeout
        self.fallback_to_stub = fallback_to_stub
        # Scoring config: instance attributes with env var / default fallback
        self.scoring_mode = scoring_mode or os.environ.get("SCORING_MODE", "ai")
        # Row-level LLM during crawl is deferred to ai_content_pipeline by default
        # (OPENCLAW_SKIP_ROW_SCORE=1 keeps crawl fast; pipeline batch-scores later).
        if row_level_llm is not None:
            self.row_level_llm = bool(row_level_llm)
        else:
            self.row_level_llm = os.environ.get("OPENCLAW_SKIP_ROW_SCORE", "1").lower() not in (
                "1",
                "true",
                "yes",
            )
        self.max_posts = max_posts or int(os.environ.get("OPENCLAW_MAX_POSTS", "20"))
        self.min_content_chars = int(os.environ.get("PARSE_MIN_CONTENT_CHARS", "40"))
        self.stub = StubProvider()
        # AI sentiment analyzer (optional local transformers pipeline)
        try:
            self.ai_analyzer = AISentimentAnalyzer(
                enable_fusion=(self.scoring_mode or "").lower()
                in {"hybrid", "fuse", "fusion"}
            )
            logger.info(
                "AI analyzer initialized (OpenClaw ready=%s)",
                getattr(self.ai_analyzer, "is_openclaw_ready", lambda: False)(),
            )
        except Exception as exc:
            logger.warning("AI analyzer init failed: %s", exc)
            self.ai_analyzer = None
        self._browser = None
        try:
            from opinion_trading.integrations.browser_collect import (
                BROWSER_PLATFORMS,
                BrowserCollector,
            )

            self._browser_platforms = BROWSER_PLATFORMS
            self._browser = BrowserCollector()
        except Exception as exc:
            logger.debug("BrowserCollector unavailable: %s", exc)
            self._browser_platforms = frozenset({"xueqiu", "weibo", "douyin"})
            self._browser = None

    def fetch(self, platform: str, symbol: str, trade_date: date) -> Dict[str, float]:
        try:
            raw_rows = self.collect_raw_posts(
                platform=platform, symbol=symbol, trade_date=trade_date
            )
            if raw_rows:
                sentiment = self._score_text(
                    " ".join(
                        f"{row.get('title', '')} {row.get('content', '')}"
                        for row in raw_rows
                    )
                )
                return {
                    "sentiment_score": sentiment,
                    "post_count": len(raw_rows),
                    "source": str(
                        raw_rows[0].get(
                            "source_page",
                            raw_rows[0].get("url", self._build_url(platform, symbol)),
                        )
                    ),
                }

            url = self._build_url(platform=platform, symbol=symbol)
            html = self._download_html(url)
            snippets = self._extract_text_snippets(html)
            sentiment = self._score_text(" ".join(snippets))

            return {
                "sentiment_score": sentiment,
                "post_count": max(1, len(snippets)),
                "source": url,
            }
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError):
            logger.warning("HTTP error in fetch(%s, %s), stub fallback", platform, symbol)
            if not self.fallback_to_stub:
                raise
            row = self.stub.fetch(
                platform=platform, symbol=symbol, trade_date=trade_date
            )
            row["source"] = f"fallback://{platform}"
            return row
        except Exception:
            logger.exception("Unexpected error in fetch(%s, %s)", platform, symbol)
            if not self.fallback_to_stub:
                raise
            row = self.stub.fetch(
                platform=platform, symbol=symbol, trade_date=trade_date
            )
            row["source"] = f"fallback://{platform}"
            return row

    def collect_raw_posts(
        self, platform: str, symbol: str, trade_date: date, max_posts: int | None = None
    ) -> List[Dict[str, str]]:
        if max_posts is None:
            max_posts = getattr(self, "max_posts", None) or int(
                os.environ.get("OPENCLAW_MAX_POSTS", "20")
            )
        logger.info("Collecting %s/%s max_posts=%d", platform, symbol, max_posts)
        list_url = self._build_url(platform=platform, symbol=symbol)

        # JS-heavy platforms: Playwright + Cookie first
        browser_platforms = getattr(
            self, "_browser_platforms", frozenset({"xueqiu", "weibo", "douyin"})
        )
        if platform in browser_platforms and self._browser is not None:
            try:
                browsed = self._browser.collect(
                    platform=platform,
                    symbol=symbol,
                    list_url=list_url,
                    trade_date=trade_date,
                    max_posts=max_posts,
                )
                if browsed:
                    return [self._finalize_collected_row(r) for r in browsed]
            except Exception as exc:
                logger.warning("Browser path error %s/%s: %s", platform, symbol, exc)

        try:
            html = self._download_html(list_url)

            if platform in {_PLATFORM_GUBA, _PLATFORM_EASTMONEY}:
                rows = self._collect_guba_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )
            elif platform == _PLATFORM_SINA:
                rows = self._collect_generic_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )
            elif platform == _PLATFORM_DOUYIN:
                rows = self._collect_douyin_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )
            else:
                rows = self._collect_generic_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )

            if rows:
                logger.info("Collected %d rows from %s/%s", len(rows), platform, symbol)
                return rows

            logger.warning("Zero rows from %s/%s", platform, symbol)
            # Weak platforms: never inject stub/placeholder pollution
            if platform in browser_platforms:
                return []
            return self._collect_fallback_rows(list_url, platform, symbol, trade_date)
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            logger.warning("HTTP error collecting %s/%s: %s", platform, symbol, exc)
            if platform in browser_platforms:
                return []
            if not self.fallback_to_stub:
                raise
            return self._collect_stub_rows(platform, symbol, trade_date)
        except Exception as exc:
            logger.exception(
                "Unexpected error collecting %s/%s: %s", platform, symbol, exc
            )
            if platform in browser_platforms:
                return []
            if not self.fallback_to_stub:
                raise
            return self._collect_stub_rows(platform, symbol, trade_date)

    def _finalize_collected_row(self, row: Dict[str, str]) -> Dict[str, str]:
        """Normalize browser rows through _build_raw_row fields when possible."""
        if "keyword_score" in row and "score_source" in row:
            # ensure keyword score present without forcing LLM
            title = str(row.get("title", ""))
            content = str(row.get("content", ""))
            pos = sum((title + " " + content).count(w) for w in self._POSITIVE_WORDS)
            neg = sum((title + " " + content).count(w) for w in self._NEGATIVE_WORDS)
            kw = (pos - neg) / (pos + neg + 5) if (pos + neg + 5) else 0.0
            row["keyword_score"] = float(kw)
            if not row.get("score_source") or row.get("score_source") == "pending_ai":
                row["ai_score"] = float(kw)
                row["score_source"] = "pending_ai"
            return row
        return self._build_raw_row(
            trade_date=date.fromisoformat(str(row.get("trade_date"))[:10])
            if row.get("trade_date")
            else date.today(),
            platform=str(row.get("platform", "")),
            symbol=str(row.get("symbol", "")),
            title=str(row.get("title", "")),
            summary=str(row.get("summary", "")),
            post_time=str(row.get("post_time", "")),
            content=str(row.get("content", "")),
            url=str(row.get("url", "")),
            source_page=str(row.get("source_page", "")),
            is_noise=bool(row.get("is_noise", False)),
            capture_status=str(row.get("capture_status", "success")),
            failure_reason=str(row.get("failure_reason", "")),
        )

    def _collect_guba_rows(
        self,
        list_url: str,
        html: str,
        platform: str,
        symbol: str,
        trade_date: date,
        max_posts: int,
    ) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        stock_code = symbol.split(".", maxsplit=1)[0]
        article_urls: List[str] = []
        for anchor in soup.select('a[href^="/news,"]'):
            href = str(anchor.get("href", "")).strip()
            if stock_code not in href or href in article_urls:
                continue

            # prefer anchors that look like article links (contain date/time or longer titles)
            anchor_text = self._clean_text(anchor.get_text(" ", strip=True))
            parent_text = self._clean_text(
                anchor.parent.get_text(" ", strip=True) if anchor.parent else ""
            )
            if not anchor_text:
                continue

            looks_like_article = False
            if len(anchor_text) >= 20:
                looks_like_article = True
            if any(
                token in anchor_text + parent_text
                for token in ("年", "20", ":", "发布", "时间")
            ):
                looks_like_article = True

            if not looks_like_article:
                # still accept a limited number of shorter links as fallback
                if len(article_urls) >= max(1, max_posts // 3):
                    continue

            article_urls.append(href)
            if len(article_urls) >= max_posts:
                break

        rows: List[Dict[str, str]] = []
        for href in article_urls:
            # skip non-article / sticky noise links
            href_l = href.lower()
            if any(x in href_l for x in ("ad.", "advert", "help,", "about,")):
                continue
            article_url = urljoin("https://guba.eastmoney.com", href)
            try:
                article_html = self._download_html(article_url)
                row = self._parse_article_page(
                    platform=platform,
                    symbol=symbol,
                    trade_date=trade_date,
                    page_url=list_url,
                    article_url=article_url,
                    html=article_html,
                )
            except Exception as exc:
                logger.debug("article fetch failed %s: %s", article_url[:80], exc)
                continue
            # Do not pollute aggregates with empty parse failures
            if row.get("capture_status") == "fail":
                continue
            if row.get("capture_status") == "fallback" and not str(
                row.get("content") or ""
            ).strip():
                continue
            rows.append(row)
        return rows

    def _collect_generic_rows(
        self,
        list_url: str,
        html: str,
        platform: str,
        symbol: str,
        trade_date: date,
        max_posts: int,
    ) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        if platform == "sina_finance":
            return self._collect_sina_rows(
                list_url, soup, symbol, trade_date, max_posts=max_posts
            )

        rows: List[Dict[str, str]] = []
        seen: set[str] = set()

        for node in soup.select("a, h1, h2, h3, p, li, div, span"):
            text = self._clean_text(node.get_text(" ", strip=True))
            if not self._looks_like_content(text):
                continue

            key = text[:120]
            if key in seen:
                continue
            seen.add(key)

            href = self._clean_text(node.get("href", "")) if node.name == "a" else ""
            article_url = urljoin(list_url, href) if href else list_url
            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform=platform,
                    symbol=symbol,
                    title=text,
                    summary=text,
                    post_time=self._extract_time(text, trade_date=trade_date),
                    content=text,
                    url=article_url,
                    source_page=list_url,
                    is_noise=self._is_noise_text(text),
                    capture_status="success",
                    failure_reason="",
                )
            )
            if len(rows) >= max_posts:
                break

        return rows

    def _collect_sina_rows(
        self,
        list_url: str,
        soup: BeautifulSoup,
        symbol: str,
        trade_date: date,
        max_posts: int,
    ) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        seen: set[str] = set()

        for anchor in soup.select("a"):
            anchor_text = self._clean_text(anchor.get_text(" ", strip=True))
            if not anchor_text or not self._looks_like_content(anchor_text):
                continue

            parent_text = self._clean_text(
                anchor.parent.get_text(" ", strip=True)
                if anchor.parent
                else anchor_text
            )
            time_text = self._extract_time(parent_text, trade_date=trade_date)

            if not time_text:
                continue

            if len(anchor_text) < 8 or self._is_noise_text(anchor_text):
                continue

            key = f"{time_text}|{anchor_text[:120]}"
            if key in seen:
                continue
            seen.add(key)

            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform="sina_finance",
                    symbol=symbol,
                    title=anchor_text,
                    summary=parent_text,
                    post_time=time_text,
                    content=parent_text,
                    url=urljoin(list_url, self._clean_text(anchor.get("href", "")))
                    if anchor.get("href")
                    else list_url,
                    source_page=list_url,
                    is_noise=self._is_noise_text(parent_text),
                    capture_status="success",
                    failure_reason="",
                )
            )

            if len(rows) >= max_posts:
                break

        return rows

    def _collect_douyin_rows(
        self,
        list_url: str,
        html: str,
        platform: str,
        symbol: str,
        trade_date: date,
        max_posts: int,
    ) -> List[Dict[str, str]]:
        """Best-effort Douyin scraper: extract structured JSON-LD, meta tags, or visible text.

        Douyin is JS-heavy so this is best-effort and may return few rows. Falls back
        to generic text extraction when structured metadata is available.
        """
        soup = BeautifulSoup(html, "lxml")
        rows: List[Dict[str, str]] = []

        # try JSON-LD structured data
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                text = self._clean_text(script.string or "")
                if not text:
                    continue
                import json

                payload = json.loads(text)
                # payload may be an object or list
                items = payload if isinstance(payload, list) else [payload]
                for item in items:
                    title = item.get("headline") or item.get("name") or ""
                    desc = item.get("description") or ""
                    if title or desc:
                        rows.append(
                            self._build_raw_row(
                                trade_date=trade_date,
                                platform=platform,
                                symbol=symbol,
                                title=title or desc[:120],
                                summary=(desc[:300] if desc else title[:300]),
                                post_time=self._extract_time(
                                    desc or title, trade_date=trade_date
                                ),
                                content=desc or title,
                                url=list_url,
                                source_page=list_url,
                                is_noise=self._is_noise_text((title + " " + desc)),
                                capture_status="success",
                                failure_reason="",
                            )
                        )
                        if len(rows) >= max_posts:
                            return rows
            except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
                logger.debug("Skipping malformed JSON-LD in douyin: %s", exc)
                continue

        # fallback to og/meta tags
        og_title = (
            (soup.select_one('meta[property="og:title"]') or {}).get("content")
            if soup.select_one('meta[property="og:title"]')
            else None
        )
        og_desc = (
            (soup.select_one('meta[property="og:description"]') or {}).get("content")
            if soup.select_one('meta[property="og:description"]')
            else None
        )
        if og_title or og_desc:
            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform=platform,
                    symbol=symbol,
                    title=self._short_title(og_title or og_desc or ""),
                    summary=(og_desc or og_title or "")[:300],
                    post_time=self._extract_time(
                        og_desc or og_title or "", trade_date=trade_date
                    ),
                    content=(og_desc or og_title or ""),
                    url=list_url,
                    source_page=list_url,
                    is_noise=self._is_noise_text((og_title or "" + og_desc or "")),
                    capture_status="success",
                    failure_reason="",
                )
            )

        # last-resort: extract visible text blocks similar to generic collector
        if not rows:
            seen: set[str] = set()
            for node in soup.select("p, h1, h2, h3, div, span"):
                text = self._clean_text(node.get_text(" ", strip=True))
                if not self._looks_like_content(text):
                    continue
                key = text[:160]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    self._build_raw_row(
                        trade_date=trade_date,
                        platform=platform,
                        symbol=symbol,
                        title=text[:120],
                        summary=text[:300],
                        post_time=self._extract_time(text, trade_date=trade_date),
                        content=text,
                        url=list_url,
                        source_page=list_url,
                        is_noise=self._is_noise_text(text),
                        capture_status="success",
                        failure_reason="",
                    )
                )
                if len(rows) >= max_posts:
                    break

        return rows

    def _parse_article_page(
        self,
        platform: str,
        symbol: str,
        trade_date: date,
        page_url: str,
        article_url: str,
        html: str,
    ) -> Dict[str, str]:
        soup = BeautifulSoup(html, "lxml")
        # strip common chrome / sidebars before extraction
        for junk in soup.select(
            "script, style, nav, header, footer, .footer, .header, "
            "#header, #footer, .nav, .side, .sidebar, .ads, .ad, "
            ".guba_left, .guba_right, .rightmodule"
        ):
            junk.decompose()

        page_title = self._extract_page_title(soup)
        text = self._clean_text(soup.get_text(" ", strip=True))

        content_candidate = ""
        for sel in (
            "div#zwconbody",
            "div#zwconttbt",
            "div#zwcon",
            "div.xeditor_content",
            "div.stockcodec",
            "div#ContentBody",
            "div.article-content",
            "div#article",
            "div.article",
            "div#content",
            "div.main-content",
            "div.content",
            "div.zwconbody",
            "div.newstext",
        ):
            node = soup.select_one(sel)
            if node:
                candidate = self._clean_text(node.get_text(" ", strip=True))
                if len(candidate) >= self.min_content_chars:
                    content_candidate = candidate
                    break

        if not content_candidate:
            paragraphs = [
                self._clean_text(p.get_text(" ", strip=True))
                for p in soup.find_all(["p", "div"])
                if p
            ]
            paragraphs = sorted(paragraphs, key=lambda x: len(x), reverse=True)
            if paragraphs:
                best = paragraphs[0]
                if len(best) >= self.min_content_chars:
                    content_candidate = best

        content = (
            content_candidate
            or self._extract_article_content(text)
            or self._normalize_content(text)
        )
        content = strip_boilerplate(content) or strip_boilerplate(page_title) or content

        title = self._short_title(page_title or content or text)
        title = strip_boilerplate(title) or title
        post_time = self._extract_time(text, trade_date=trade_date)

        # Prefer title+summary success over empty fallback pollution
        min_ok = self.min_content_chars
        if len(content) < min_ok:
            summary_blob = self._clean_text(f"{title} {content}").strip()
            if len(summary_blob) >= 16 and title:
                return {
                    **self._build_raw_row(
                        trade_date=trade_date,
                        platform=platform,
                        symbol=symbol,
                        title=title,
                        summary=summary_blob[:300],
                        post_time=post_time or trade_date.isoformat(),
                        content=summary_blob[:800],
                        url=article_url,
                        source_page=page_url,
                        is_noise=self._is_noise_text(summary_blob),
                        capture_status="success",
                        failure_reason="",
                    )
                }
            return {
                **self._build_raw_row(
                    trade_date=trade_date,
                    platform=platform,
                    symbol=symbol,
                    title=self._short_title(page_title or text[:120]),
                    summary="",
                    post_time=post_time or trade_date.isoformat(),
                    content="",
                    url=article_url,
                    source_page=page_url,
                    is_noise=True,
                    capture_status="fail",
                    failure_reason="parsed content too short",
                )
            }

        return {
            **self._build_raw_row(
                trade_date=trade_date,
                platform=platform,
                symbol=symbol,
                title=title,
                summary=content[:300],
                post_time=post_time,
                content=content,
                url=article_url,
                source_page=page_url,
                is_noise=self._is_noise_text(f"{title} {content}"),
                capture_status="success",
                failure_reason="",
            )
        }

    def _collect_fallback_rows(
        self, list_url: str, platform: str, symbol: str, trade_date: date
    ) -> List[Dict[str, str]]:
        title = f"{symbol} {platform} fallback record"
        return [
            self._build_raw_row(
                trade_date=trade_date,
                platform=platform,
                symbol=symbol,
                title=title,
                summary="Fallback row generated when live page parsing returned no rows.",
                post_time=trade_date.isoformat(),
                content=f"Fallback row generated for {platform} when live page parsing returned no rows.",
                url=list_url,
                source_page=list_url,
                is_noise=True,
                capture_status="fallback",
                failure_reason=f"no rows parsed from live {platform} page",
            )
        ]

    def _collect_stub_rows(
        self, platform: str, symbol: str, trade_date: date
    ) -> List[Dict[str, str]]:
        return [
            self._build_raw_row(
                trade_date=trade_date,
                platform=platform,
                symbol=symbol,
                title=f"{symbol} {platform} stub record",
                summary=f"Stub fallback summary for {platform}.",
                post_time=trade_date.isoformat(),
                content=f"Stub fallback content for {platform}.",
                url=f"fallback://{platform}",
                source_page=f"fallback://{platform}",
                is_noise=True,
                capture_status="fallback",
                failure_reason=f"stub fallback used for {platform}",
            )
        ]

    def _build_url(self, platform: str, symbol: str) -> str:
        code = self._to_cn_market_code(symbol)

        if platform in {"guba", "eastmoney"}:
            return f"https://guba.eastmoney.com/list,{code}.html"
        if platform == "sina_finance":
            return f"https://finance.sina.com.cn/realstock/company/{code}/nc.shtml"
        if platform == "weibo":
            return f"https://s.weibo.com/weibo?q={symbol}"
        if platform == "xueqiu":
            return f"https://xueqiu.com/S/{code}"
        if platform == "douyin":
            # Douyin is JS-heavy; use search page as a best-effort entrypoint
            # example: https://www.douyin.com/search/{keyword}
            return f"https://www.douyin.com/search/{symbol}"

        raise ValueError(f"Unsupported platform: {platform}")

    def _download_html(self, url: str) -> str:
        # 1) 尝试缓存
        cached = _read_html_cache(url)
        if cached is not None:
            return cached

        # 2) 频率控制
        _rate_limit(url)

        # 3) 实际请求
        logger.info("Downloading %s", url[:160])
        try:
            response = requests.get(
                url, headers=self._HEADERS, timeout=self.timeout
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        except requests.Timeout:
            logger.warning("Timeout downloading %s (%ds)", url[:120], self.timeout)
            raise
        except requests.ConnectionError as exc:
            logger.warning("Connection error %s: %s", url[:120], exc)
            raise
        except requests.HTTPError as exc:
            logger.warning("HTTP %s for %s", exc.response.status_code, url[:120])
            raise
        except Exception:
            logger.exception("Unexpected error downloading %s", url[:120])
            raise

        # 4) 写入缓存
        _write_html_cache(url, response.text)
        return response.text

    def _extract_text_snippets(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        snippets: List[str] = []

        for node in soup.select("title, h1, h2, h3, p, a"):
            text = self._clean_text(node.get_text(" ", strip=True))
            if self._looks_like_content(text):
                snippets.append(text)

        return snippets[:300]

    def _score_text(self, text: str) -> float:
        if not text:
            return 0.0

        # Prefer AI analyzer if available
        if getattr(self, "ai_analyzer", None):
            try:
                scores = self.ai_analyzer.score_texts([text])
                if scores:
                    return float(scores[0])
            except Exception as exc:
                logger.debug("AI score_text failed, using keyword fallback: %s", exc)

        # fallback keyword heuristic
        pos = sum(text.count(word) for word in self._POSITIVE_WORDS)
        neg = sum(text.count(word) for word in self._NEGATIVE_WORDS)

        raw = (pos - neg) / (pos + neg + 5)
        return max(-1.0, min(1.0, float(raw)))

    def _extract_page_title(self, soup: BeautifulSoup) -> str:
        if soup.title and soup.title.get_text(strip=True):
            return self._short_title(soup.title.get_text(" ", strip=True))
        return ""

    def _extract_article_content(self, text: str) -> str:
        content = text
        if "来源：" in content:
            content = content.split("来源：", maxsplit=1)[1]
        for marker in ["（文章来源", "[点击查看原文]", "举报", "郑重声明", "免责声明", "请勿相信"]:
            if marker in content:
                content = content.split(marker, maxsplit=1)[0]
        return self._normalize_content(content)

    def _extract_time(self, text: str, trade_date: date | None = None) -> str:
        patterns = [
            r"20\d{2}-\d{1,2}-\d{1,2}[ T]\d{2}:\d{2}:\d{2}",
            r"20\d{2}-\d{1,2}-\d{1,2}[ T]\d{2}:\d{2}",
            r"20\d{2}/\d{1,2}/\d{1,2}[ T]\d{2}:\d{2}:\d{2}",
            r"20\d{2}/\d{1,2}/\d{1,2}[ T]\d{2}:\d{2}",
            r"20\d{2}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}(:\d{2})?",
            r"20\d{2}年\d{1,2}月\d{1,2}日",
            r"\(\d{2}-\d{2}\)",
            r"\d{2}-\d{2}",
            r"\d{1,2}-\d{1,2}\s+\d{2}:\d{2}(?::\d{2})?",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(0).strip("()")
                if re.fullmatch(r"\d{2}-\d{2}", value) and trade_date is not None:
                    return f"{trade_date.year}-{value}"
                return value
        return ""

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _short_title(self, value: str) -> str:
        text = self._clean_text(value)
        if "_" in text:
            text = text.split("_", maxsplit=1)[0]
        return text[:120]

    def _normalize_content(self, value: str) -> str:
        stripped = strip_boilerplate(self._clean_text(value))
        return stripped if stripped else self._clean_text(value)[:800]

    def _build_summary(self, title: str, content: str) -> str:
        title_text = self._clean_text(title)
        content_text = self._clean_text(content)
        if not title_text and not content_text:
            return ""
        if not content_text:
            return title_text[:120]
        if title_text:
            return f"{title_text} | {content_text[:80]}"[:180]
        return content_text[:180]

    def _build_raw_row(
        self,
        *,
        trade_date: date,
        platform: str,
        symbol: str,
        title: str,
        summary: str | None,
        post_time: str,
        content: str,
        url: str,
        source_page: str,
        is_noise: bool,
        capture_status: str,
        failure_reason: str,
    ) -> Dict[str, str]:
        summary_text = self._build_summary(
            summary if summary is not None else title, content
        )
        norm_content = self._normalize_content(content)

        # ── 模式 A：关键词分（始终计算，作为保底）────────────────────────────────
        pos = sum((title + " " + content).count(word) for word in self._POSITIVE_WORDS)
        neg = sum((title + " " + content).count(word) for word in self._NEGATIVE_WORDS)
        keyword_score = (pos - neg) / (pos + neg + 5) if (pos + neg + 5) != 0 else 0.0

        # ── 模式 B：逐条 LLM（默认关闭；由 ai_content_pipeline 批量打分）────────
        ai_score = ""
        skip_row_ai = not getattr(self, "row_level_llm", False)
        score_source = "pending_ai" if skip_row_ai else "keyword"
        if not skip_row_ai and getattr(self, "ai_analyzer", None):
            try:
                results = self.ai_analyzer.analyze_texts([f"{title} {content}"])
                if results:
                    ai_score = results[0].score
                    src = results[0].source
                    score_source = (
                        "openclaw"
                        if src in {"openclaw", "transformers", "hybrid"}
                        else "keyword"
                    )
            except Exception as exc:
                logger.debug("Row-level AI score failed: %s", exc)
                ai_score = ""
        # 未开启或失败时，ai_score 回退为关键词分（两列始终都有值）
        if ai_score == "":
            ai_score = float(keyword_score)
            if score_source == "pending_ai":
                pass
            else:
                score_source = "keyword"

        return {
            "trade_date": trade_date.isoformat(),
            "platform": platform,
            "symbol": symbol,
            "title": self._short_title(title),
            "summary": summary_text,
            "post_time": post_time,
            "content": norm_content,
            "url": url,
            "source_page": source_page,
            "fetch_time": datetime.now().isoformat(),
            "is_noise": is_noise,
            "capture_status": capture_status,
            "failure_reason": failure_reason,
            "keyword_score": float(keyword_score),
            "ai_score": float(ai_score) if ai_score != "" else "",
            "score_source": score_source,
        }

    def _looks_like_content(self, text: str) -> bool:
        cleaned = self._clean_text(text)
        if len(cleaned) < 8:
            return False
        if self._is_noise_text(cleaned):
            return False
        return True

    def _is_noise_text(self, text: str) -> bool:
        low = self._clean_text(text).lower()
        if not low:
            return True
        if is_boilerplate(text):
            return True
        if len(low) < 12:
            return True
        noise_tokens = [
            "登录",
            "注册",
            "下载app",
            "扫一扫",
            "免责声明",
            "返回",
            "举报",
            "郑重声明",
            "风险自担",
            "意见与建议",
            "请勿相信",
            "远离非法证券活动",
            "点击查看原文",
            "扫一扫下载",
            "东方财富产品",
        ]
        hits = sum(1 for token in noise_tokens if token.lower() in low)
        return hits >= 2

    def _to_cn_market_code(self, symbol: str) -> str:
        symbol = symbol.upper()
        if "." not in symbol:
            return symbol.lower()

        stock, market = symbol.split(".", maxsplit=1)
        if market == "SH":
            return f"sh{stock}"
        if market == "SZ":
            return f"sz{stock}"
        return symbol.lower()
