"""Playwright-based collectors for JS-heavy platforms (xueqiu / weibo / douyin).

Cookies are read from env (never commit secrets):
  XUEQIU_COOKIE, WEIBO_COOKIE, DOUYIN_COOKIE
  or PLATFORM_COOKIES_JSON={"xueqiu":"...","weibo":"...","douyin":"..."}
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

BROWSER_PLATFORMS = frozenset({"xueqiu", "weibo", "douyin"})


def _parse_cookie_header(raw: str, domain: str) -> List[Dict[str, Any]]:
    """Convert 'a=1; b=2' cookie header into Playwright cookie dicts."""
    cookies: List[Dict[str, Any]] = []
    for part in str(raw or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name, value = name.strip(), value.strip()
        if not name:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
            }
        )
    return cookies


def load_platform_cookie(platform: str) -> str:
    blob = os.environ.get("PLATFORM_COOKIES_JSON", "").strip()
    if blob:
        try:
            data = json.loads(blob)
            if isinstance(data, dict) and platform in data:
                return str(data[platform] or "")
        except json.JSONDecodeError:
            logger.warning("PLATFORM_COOKIES_JSON is not valid JSON")
    env_key = {
        "xueqiu": "XUEQIU_COOKIE",
        "weibo": "WEIBO_COOKIE",
        "douyin": "DOUYIN_COOKIE",
    }.get(platform, "")
    return os.environ.get(env_key, "").strip() if env_key else ""


def cookie_domain_for(platform: str) -> str:
    return {
        "xueqiu": ".xueqiu.com",
        "weibo": ".weibo.com",
        "douyin": ".douyin.com",
    }.get(platform, "")


def extract_posts_from_html(
    html: str,
    *,
    platform: str,
    symbol: str,
    list_url: str,
    trade_date: date,
    max_posts: int = 20,
) -> List[Dict[str, str]]:
    """Pure HTML extraction (unit-testable without Playwright)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html or "", "lxml")
    rows: List[Dict[str, str]] = []
    seen: set[str] = set()

    def _clean(t: str) -> str:
        return re.sub(r"\s+", " ", str(t or "")).strip()

    def _add(title: str, content: str, url: str = "", post_time: str = "") -> None:
        title, content = _clean(title), _clean(content)
        blob = content or title
        if len(blob) < 8:
            return
        key = blob[:120]
        if key in seen:
            return
        # skip obvious placeholders / login walls
        low = blob.lower()
        if any(x in low for x in ("请登录", "扫码登录", "stub record", "fallback record")):
            return
        seen.add(key)
        rows.append(
            {
                "trade_date": trade_date.isoformat(),
                "platform": platform,
                "symbol": symbol,
                "title": title[:120] or blob[:80],
                "summary": blob[:300],
                "post_time": post_time or trade_date.isoformat(),
                "content": blob[:2000],
                "url": url or list_url,
                "source_page": list_url,
                "fetch_time": datetime.now().isoformat(),
                "is_noise": False,
                "capture_status": "success",
                "failure_reason": "",
                "keyword_score": 0.0,
                "ai_score": 0.0,
                "score_source": "pending_ai",
            }
        )

    if platform == "xueqiu":
        for node in soup.select(
            "article, .timeline__item, .status-list .status-item, "
            ".home-timeline .timeline__item, .status-content, .stock-timeline-item"
        ):
            text = _clean(node.get_text(" ", strip=True))
            if len(text) < 12:
                continue
            link = node.select_one("a[href]")
            href = ""
            if link and link.get("href"):
                href = str(link.get("href"))
                if href.startswith("/"):
                    href = "https://xueqiu.com" + href
            _add(text[:80], text, href)
            if len(rows) >= max_posts:
                break
        if not rows:
            code = symbol.split(".")[0]
            for node in soup.select("p, div, span"):
                text = _clean(node.get_text(" ", strip=True))
                if not (20 <= len(text) <= 800):
                    continue
                if code in text or any(
                    k in text
                    for k in ("涨", "跌", "股", "业绩", "财报", "买入", "卖出", "看多", "看空", "$")
                ):
                    _add(text[:80], text)
                if len(rows) >= max_posts:
                    break

    elif platform == "weibo":
        for node in soup.select(
            ".card-wrap, .card-feed, .txt, .content, [node-type='feed_list_content'], "
            ".woo-box-flex .txt"
        ):
            text = _clean(node.get_text(" ", strip=True))
            if len(text) < 12:
                continue
            _add(text[:80], text)
            if len(rows) >= max_posts:
                break
        if not rows:
            for node in soup.select("p, div"):
                text = _clean(node.get_text(" ", strip=True))
                if len(text) >= 30 and not text.startswith("热搜"):
                    _add(text[:80], text)
                if len(rows) >= max_posts:
                    break

    else:  # douyin
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                payload = json.loads(script.string or "")
                items = payload if isinstance(payload, list) else [payload]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    title = item.get("headline") or item.get("name") or ""
                    desc = item.get("description") or ""
                    if title or desc:
                        _add(str(title), str(desc or title))
                    if len(rows) >= max_posts:
                        return rows
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
        for node in soup.select("[data-e2e='search-card-desc'], .search-result-card, p, h1, h2"):
            text = _clean(node.get_text(" ", strip=True))
            if len(text) >= 16:
                _add(text[:80], text)
            if len(rows) >= max_posts:
                break

    return rows[:max_posts]


class BrowserCollector:
    """Headless Chromium fetcher with optional platform cookies."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 45000,
        enabled: bool | None = None,
    ) -> None:
        if enabled is None:
            enabled = os.environ.get("BROWSER_COLLECT_ENABLED", "1").lower() not in (
                "0",
                "false",
                "no",
            )
        self.enabled = enabled
        self.headless = headless
        self.timeout_ms = timeout_ms

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        try:
            import playwright  # noqa: F401

            return True
        except ImportError:
            return False

    def collect(
        self,
        *,
        platform: str,
        symbol: str,
        list_url: str,
        trade_date: date,
        max_posts: int = 20,
    ) -> List[Dict[str, str]]:
        if platform not in BROWSER_PLATFORMS:
            return []
        if not self.is_available():
            logger.warning("Playwright not available; skip browser collect for %s", platform)
            return []

        from playwright.sync_api import sync_playwright

        cookie_raw = load_platform_cookie(platform)
        domain = cookie_domain_for(platform)
        rows: List[Dict[str, str]] = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="zh-CN",
                )
                if cookie_raw and domain:
                    context.add_cookies(_parse_cookie_header(cookie_raw, domain))
                    # also set parent domain variants
                    host = urlparse(list_url).hostname or ""
                    if host and not host.startswith("."):
                        context.add_cookies(_parse_cookie_header(cookie_raw, host))

                page = context.new_page()
                page.set_default_timeout(self.timeout_ms)
                page.goto(list_url, wait_until="domcontentloaded")
                try:
                    page.wait_for_timeout(2500)
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                # mild scroll to trigger lazy content
                try:
                    page.mouse.wheel(0, 2400)
                    page.wait_for_timeout(800)
                except Exception:
                    pass
                html = page.content()
                context.close()
                browser.close()
            rows = extract_posts_from_html(
                html,
                platform=platform,
                symbol=symbol,
                list_url=list_url,
                trade_date=trade_date,
                max_posts=max_posts,
            )
            logger.info(
                "Browser collect %s/%s -> %d rows (cookie=%s)",
                platform,
                symbol,
                len(rows),
                "yes" if cookie_raw else "no",
            )
        except Exception as exc:
            logger.warning("Browser collect failed %s/%s: %s", platform, symbol, exc)
            return []

        return rows
