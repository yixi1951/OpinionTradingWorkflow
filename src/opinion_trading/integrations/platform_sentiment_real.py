from __future__ import annotations

import os
import json
import re
from datetime import date, datetime
from typing import Dict, List
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from opinion_trading.integrations.platform_sentiment_stub import (
    PlatformSentimentProvider as StubProvider,
)
from opinion_trading.core.ai_sentiment import AISentimentAnalyzer

import sys
from pathlib import Path as _Path

_scripts_dir = _Path(__file__).resolve().parents[3] / "scripts"
if _scripts_dir.exists() and str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))
try:
    from text_quality import is_boilerplate, is_news_headline, is_user_comment, strip_boilerplate
except ImportError:

    def is_boilerplate(text: str) -> bool:  # type: ignore[misc]
        return False

    def is_news_headline(text: str, platform: str = "") -> bool:  # type: ignore[misc]
        return len(str(text or "")) > 120

    def is_user_comment(text: str, platform: str = "", url: str = "") -> bool:  # type: ignore[misc]
        return True

    def strip_boilerplate(text: str, *, max_len: int = 800) -> str:  # type: ignore[misc]
        return str(text or "")[:max_len]


class RealPlatformSentimentProvider:
    """Fetches text from real platform pages and derives a simple sentiment score."""

    _STOCK_NAMES: Dict[str, str] = {
        "600519": "贵州茅台",
        "000001": "平安银行",
        "601318": "中国平安",
    }

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    _POSITIVE_WORDS = ["上涨", "利好", "突破", "增长", "看多", "反弹", "盈利", "强势", "买入", "乐观"]
    _NEGATIVE_WORDS = ["下跌", "利空", "风险", "暴跌", "看空", "回撤", "亏损", "弱势", "卖出", "悲观"]
    _GUBA_BLOCKED_TITLES = ("身份核实", "访问验证", "安全验证", "滑动验证")

    def __init__(self, timeout: int = 10, fallback_to_stub: bool = True) -> None:
        self.timeout = timeout
        self.fallback_to_stub = fallback_to_stub
        self.stub = StubProvider()
        # AI sentiment analyzer (optional local transformers pipeline)
        try:
            self.ai_analyzer = AISentimentAnalyzer()
        except Exception:
            self.ai_analyzer = None

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
        except Exception:
            if not self.fallback_to_stub:
                raise

            row = self.stub.fetch(
                platform=platform, symbol=symbol, trade_date=trade_date
            )
            row["source"] = f"fallback://{platform}"
            return row

    def collect_raw_posts(
        self, platform: str, symbol: str, trade_date: date, max_posts: int = 18
    ) -> List[Dict[str, str]]:
        try:
            list_url = self._build_url(platform=platform, symbol=symbol)
            html = self._download_html(list_url)

            if platform in {"guba", "eastmoney"}:
                rows = self._collect_guba_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )
            elif platform == "sina_finance":
                rows = self._collect_generic_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )
            elif platform == "weibo":
                rows = self._collect_weibo_rows(
                    list_url, html, symbol, trade_date, max_posts=max_posts
                )
            elif platform == "xueqiu":
                rows = self._collect_xueqiu_rows(
                    list_url, html, symbol, trade_date, max_posts=max_posts
                )
            elif platform == "douyin":
                rows = self._collect_douyin_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )
            else:
                rows = self._collect_generic_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )

            if rows:
                return self._apply_batch_ai_scores(rows)

            return self._collect_fallback_rows(list_url, platform, symbol, trade_date)
        except Exception:
            if not self.fallback_to_stub:
                raise
            return self._collect_stub_rows(platform, symbol, trade_date)

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
        entries: List[tuple[str, str, str]] = []
        seen_hrefs: set[str] = set()

        for anchor in soup.select('a[href^="/news,"]'):
            href = str(anchor.get("href", "")).strip()
            if stock_code not in href or href in seen_hrefs:
                continue

            list_title = self._clean_text(anchor.get_text(" ", strip=True))
            if not self._is_valid_guba_list_title(list_title):
                continue

            parent_text = self._clean_text(
                anchor.parent.get_text(" ", strip=True) if anchor.parent else list_title
            )
            post_time = (
                self._extract_time(parent_text, trade_date=trade_date)
                or trade_date.isoformat()
            )
            seen_hrefs.add(href)
            entries.append((href, list_title, post_time))
            if len(entries) >= max_posts:
                break

        rows: List[Dict[str, str]] = []
        for href, list_title, post_time in entries:
            article_url = urljoin("https://guba.eastmoney.com", href)
            if not self._should_fetch_guba_article(list_title):
                rows.append(
                    self._build_guba_title_row(
                        platform=platform,
                        symbol=symbol,
                        trade_date=trade_date,
                        list_title=list_title,
                        post_time=post_time,
                        article_url=article_url,
                        page_url=list_url,
                    )
                )
                continue

            try:
                article_html = self._download_html(article_url, referer=list_url)
                row = self._parse_article_page(
                    platform=platform,
                    symbol=symbol,
                    trade_date=trade_date,
                    page_url=list_url,
                    article_url=article_url,
                    html=article_html,
                    list_title_fallback=list_title,
                    post_time_hint=post_time,
                )
            except Exception:
                row = self._build_guba_title_row(
                    platform=platform,
                    symbol=symbol,
                    trade_date=trade_date,
                    list_title=list_title,
                    post_time=post_time,
                    article_url=article_url,
                    page_url=list_url,
                    failure_reason="article fetch failed",
                )

            if row.get("capture_status") == "fallback":
                row = self._build_guba_title_row(
                    platform=platform,
                    symbol=symbol,
                    trade_date=trade_date,
                    list_title=list_title,
                    post_time=post_time,
                    article_url=article_url,
                    page_url=list_url,
                    failure_reason=str(row.get("failure_reason") or "title_only"),
                )
            rows.append(row)
        return rows

    def _is_guba_blocked_title(self, title: str) -> bool:
        text = self._clean_text(title)
        if not text:
            return True
        return any(token in text for token in self._GUBA_BLOCKED_TITLES)

    def _is_valid_guba_list_title(self, title: str) -> bool:
        text = self._clean_text(title)
        if self._is_guba_blocked_title(text):
            return False
        if len(text) < 4 or len(text) > 180:
            return False
        if is_boilerplate(text):
            return False
        return True

    def _should_fetch_guba_article(self, list_title: str) -> bool:
        text = self._clean_text(list_title)
        if is_news_headline(text, "guba"):
            return True
        if len(text) >= 80:
            return True
        if "：" in text and len(text) >= 18:
            return True
        return False

    def _build_guba_title_row(
        self,
        *,
        platform: str,
        symbol: str,
        trade_date: date,
        list_title: str,
        post_time: str,
        article_url: str,
        page_url: str,
        failure_reason: str = "",
    ) -> Dict[str, str]:
        title = self._short_title(list_title)
        content = self._normalize_content(list_title)
        return self._build_raw_row(
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
            failure_reason=failure_reason,
        )

    def _decode_js_string(self, value: str) -> str:
        raw = str(value or "")
        try:
            return str(json.loads(f'"{raw}"'))
        except Exception:
            return raw.replace("\\n", " ").replace('\\"', '"').replace("\\/", "/")

    def _extract_guba_embedded_fields(self, html: str) -> tuple[str, str]:
        title = ""
        content = ""
        title_match = re.search(r'"post_title"\s*:\s*"((?:\\.|[^"\\])*)"', html)
        if title_match:
            title = self._decode_js_string(title_match.group(1))
        content_match = re.search(r'"post_content"\s*:\s*"((?:\\.|[^"\\])*)"', html)
        if content_match:
            content = self._decode_js_string(content_match.group(1))
            content = strip_boilerplate(self._clean_text(content)) or content
        return title, content

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

    def _symbol_keywords(self, symbol: str) -> tuple[str, str, str]:
        stock_code = symbol.split(".", maxsplit=1)[0]
        market_code = self._to_cn_market_code(symbol).upper()
        name = self._STOCK_NAMES.get(stock_code, stock_code)
        return stock_code, name, market_code

    def _is_waf_page(self, html: str) -> bool:
        low = html.lower()
        return "_waf_" in low or "aliyun_waf" in low or "sina visitor system" in low

    def _collect_weibo_rows(
        self,
        list_url: str,
        html: str,
        symbol: str,
        trade_date: date,
        max_posts: int,
    ) -> List[Dict[str, str]]:
        stock_code, name, _ = self._symbol_keywords(symbol)
        rows = self._collect_jin10_weibo_snapshot(symbol, trade_date, list_url)
        rows.extend(
            self._collect_web_search_rows(
                platform="weibo",
                symbol=symbol,
                trade_date=trade_date,
                queries=[
                    f"{name} 微博",
                    f"{stock_code} 微博",
                    f"{stock_code} site:weibo.com",
                ],
                max_posts=max_posts,
                source_page=list_url,
            )
        )
        if len(rows) < max_posts:
            rows.extend(
                self._collect_ths_news_rows(
                    platform="weibo",
                    symbol=symbol,
                    trade_date=trade_date,
                    max_posts=max_posts,
                    source_page=list_url,
                    keyword_filter="微博",
                )
            )
        return self._dedupe_rows(rows, max_posts)

    def _collect_xueqiu_rows(
        self,
        list_url: str,
        html: str,
        symbol: str,
        trade_date: date,
        max_posts: int,
    ) -> List[Dict[str, str]]:
        stock_code, name, market_code = self._symbol_keywords(symbol)
        rows = self._collect_xueqiu_html_rows(
            list_url, html, symbol, trade_date, max_posts=max_posts
        )
        if len(rows) < max_posts:
            rows.extend(
                self._collect_web_search_rows(
                    platform="xueqiu",
                    symbol=symbol,
                    trade_date=trade_date,
                    queries=[
                        f"{stock_code} site:xueqiu.com",
                        f"{market_code} site:xueqiu.com",
                        f"{name} 雪球",
                    ],
                    max_posts=max_posts,
                    source_page=list_url,
                )
            )
        if len(rows) < max_posts:
            rows.extend(
                self._collect_ths_news_rows(
                    platform="xueqiu",
                    symbol=symbol,
                    trade_date=trade_date,
                    max_posts=max_posts,
                    source_page=list_url,
                )
            )
        return self._dedupe_rows(rows, max_posts)

    def _collect_xueqiu_html_rows(
        self,
        list_url: str,
        html: str,
        symbol: str,
        trade_date: date,
        max_posts: int,
    ) -> List[Dict[str, str]]:
        if self._is_waf_page(html):
            return []

        soup = BeautifulSoup(html, "lxml")
        rows: List[Dict[str, str]] = []
        seen: set[str] = set()

        for block in soup.select("div.timeline, article, div[class*='timeline']"):
            anchor = block.select_one("a[href]")
            title = self._clean_text(anchor.get_text(" ", strip=True)) if anchor else ""
            if not title:
                heading = block.select_one("h1,h2,h3,h4")
                title = (
                    self._clean_text(heading.get_text(" ", strip=True))
                    if heading
                    else ""
                )
            time_node = block.select_one("span, time, .time")
            time_text = self._clean_text(time_node.get_text(" ", strip=True)) if time_node else ""
            post_time = self._extract_time(time_text or block.get_text(" ", strip=True), trade_date=trade_date)
            paragraph = block.select_one("p")
            content = self._clean_text(paragraph.get_text(" ", strip=True)) if paragraph else title
            if not self._looks_like_content(title) and not self._looks_like_content(content):
                continue

            key = title[:120]
            if key in seen:
                continue
            seen.add(key)

            href = self._clean_text(anchor.get("href", "")) if anchor else ""
            article_url = urljoin("https://xueqiu.com", href) if href else list_url
            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform="xueqiu",
                    symbol=symbol,
                    title=title,
                    summary=content[:300],
                    post_time=post_time or trade_date.isoformat(),
                    content=content,
                    url=article_url,
                    source_page=list_url,
                    is_noise=self._is_noise_text(f"{title} {content}"),
                    capture_status="success",
                    failure_reason="",
                )
            )
            if len(rows) >= max_posts:
                break

        if rows:
            return rows

        for anchor in soup.select("a[href*='/status/'], a[href*='/n/']"):
            title = self._clean_text(anchor.get_text(" ", strip=True))
            if not self._looks_like_content(title):
                continue
            key = title[:120]
            if key in seen:
                continue
            seen.add(key)
            href = self._clean_text(anchor.get("href", ""))
            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform="xueqiu",
                    symbol=symbol,
                    title=title,
                    summary=title,
                    post_time=self._extract_time(title, trade_date=trade_date)
                    or trade_date.isoformat(),
                    content=title,
                    url=urljoin("https://xueqiu.com", href),
                    source_page=list_url,
                    is_noise=self._is_noise_text(title),
                    capture_status="success",
                    failure_reason="",
                )
            )
            if len(rows) >= max_posts:
                break

        return rows

    def _build_search_url(self, engine: str, query: str, max_posts: int) -> str:
        result_count = max(max_posts * 2, 20)
        encoded = quote(query)
        if engine == "baidu":
            return f"https://www.baidu.com/s?rn={result_count}&wd={encoded}"
        if engine == "sogou":
            return f"https://www.sogou.com/web?query={encoded}"
        if engine == "bing":
            return f"https://cn.bing.com/search?q={encoded}&count={result_count}"
        raise ValueError(f"Unsupported search engine: {engine}")

    def _collect_web_search_rows(
        self,
        *,
        platform: str,
        symbol: str,
        trade_date: date,
        queries: List[str],
        max_posts: int,
        source_page: str,
    ) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        stock_code, name, _ = self._symbol_keywords(symbol)
        engines = ("baidu", "sogou", "bing")

        for query in queries:
            if len(rows) >= max_posts:
                break
            for engine in engines:
                if len(rows) >= max_posts:
                    break
                search_url = self._build_search_url(engine, query, max_posts)
                try:
                    html = self._download_html(search_url)
                except Exception:
                    continue
                parsed = self._parse_search_results(
                    engine=engine,
                    html=html,
                    platform=platform,
                    symbol=symbol,
                    trade_date=trade_date,
                    stock_code=stock_code,
                    name=name,
                    search_url=search_url,
                    source_page=source_page,
                    max_posts=max_posts - len(rows),
                )
                rows.extend(parsed)

        return self._dedupe_rows(rows, max_posts)

    def _parse_search_results(
        self,
        *,
        engine: str,
        html: str,
        platform: str,
        symbol: str,
        trade_date: date,
        stock_code: str,
        name: str,
        search_url: str,
        source_page: str,
        max_posts: int,
    ) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        rows: List[Dict[str, str]] = []
        seen: set[str] = set()

        if engine == "baidu":
            candidates = soup.select("div.result.c-container, div.c-container.result")
        elif engine == "sogou":
            candidates = soup.select("div.vrwrap, div.result")
        elif engine == "bing":
            candidates = soup.select("li.b_algo")
        else:
            return []

        for result in candidates:
            if len(rows) >= max_posts:
                break
            if engine == "bing":
                heading = result.select_one("h2")
            else:
                heading = result.select_one("h3")
            if not heading:
                continue

            title = self._clean_text(heading.get_text(" ", strip=True))
            if not self._looks_like_content(title):
                continue

            full_text = self._clean_text(result.get_text(" ", strip=True))
            if not self._matches_platform_result(
                platform, title, stock_code, name, full_text
            ):
                continue

            abstract = ""
            if engine == "baidu":
                for selector in (
                    "span.content-right_8Zs40",
                    "div.c-abstract",
                    "span.c-color-text",
                    "div.c-span-last",
                ):
                    node = result.select_one(selector)
                    if node:
                        abstract = self._clean_text(node.get_text(" ", strip=True))
                        break
            elif engine == "sogou":
                for selector in ("p", "div.str_info", "div.str-text", "div.space-txt"):
                    node = result.select_one(selector)
                    if node:
                        abstract = self._clean_text(node.get_text(" ", strip=True))
                        if abstract:
                            break
            elif engine == "bing":
                for selector in ("div.b_caption p", "p"):
                    node = result.select_one(selector)
                    if node:
                        abstract = self._clean_text(node.get_text(" ", strip=True))
                        if abstract:
                            break

            link = heading.select_one("a")
            href = self._clean_text(link.get("href", "")) if link else search_url
            if href.startswith("/"):
                if engine == "sogou":
                    href = urljoin("https://www.sogou.com", href)
                elif engine == "bing":
                    href = urljoin("https://cn.bing.com", href)

            content = abstract or title
            key = title[:120]
            if key in seen:
                continue
            seen.add(key)

            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform=platform,
                    symbol=symbol,
                    title=title,
                    summary=content[:300],
                    post_time=self._extract_time(content, trade_date=trade_date)
                    or trade_date.isoformat(),
                    content=content,
                    url=href or search_url,
                    source_page=source_page,
                    is_noise=self._is_noise_text(f"{title} {content}"),
                    capture_status="success",
                    failure_reason="",
                )
            )

        return rows

    def _collect_ths_news_rows(
        self,
        *,
        platform: str,
        symbol: str,
        trade_date: date,
        max_posts: int,
        source_page: str,
        keyword_filter: str = "",
    ) -> List[Dict[str, str]]:
        stock_code, _, _ = self._symbol_keywords(symbol)
        api_url = (
            "https://news.10jqka.com.cn/tapp/news/push/stock/"
            f"?code={stock_code}&page=1&pagesize={max_posts}"
        )
        try:
            response = requests.get(
                api_url,
                headers={**self._HEADERS, "Referer": "https://stock.10jqka.com.cn/"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []

        items = payload.get("data", {}).get("list", [])
        if not isinstance(items, list):
            return []

        rows: List[Dict[str, str]] = []
        for item in items:
            if len(rows) >= max_posts:
                break
            title = self._clean_text(str(item.get("title", "")))
            digest = self._clean_text(str(item.get("digest", "")))
            blob = f"{title} {digest}"
            if keyword_filter and keyword_filter not in blob:
                continue
            if not self._looks_like_content(title):
                continue

            ts = str(item.get("ctime") or item.get("rtime") or "").strip()
            post_time = trade_date.isoformat()
            if ts.isdigit():
                try:
                    post_time = datetime.fromtimestamp(int(ts)).isoformat(sep=" ", timespec="seconds")
                except Exception:
                    post_time = trade_date.isoformat()

            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform=platform,
                    symbol=symbol,
                    title=title,
                    summary=digest[:300] or title,
                    post_time=post_time,
                    content=digest or title,
                    url=str(item.get("url") or api_url),
                    source_page=source_page,
                    is_noise=self._is_noise_text(blob),
                    capture_status="success",
                    failure_reason="",
                )
            )

        if rows:
            return rows

        for item in items:
            if len(rows) >= max_posts:
                break
            title = self._clean_text(str(item.get("title", "")))
            digest = self._clean_text(str(item.get("digest", "")))
            if not self._looks_like_content(title):
                continue
            ts = str(item.get("ctime") or item.get("rtime") or "").strip()
            post_time = trade_date.isoformat()
            if ts.isdigit():
                try:
                    post_time = datetime.fromtimestamp(int(ts)).isoformat(sep=" ", timespec="seconds")
                except Exception:
                    post_time = trade_date.isoformat()
            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform=platform,
                    symbol=symbol,
                    title=title,
                    summary=digest[:300] or title,
                    post_time=post_time,
                    content=digest or title,
                    url=str(item.get("url") or api_url),
                    source_page=source_page,
                    is_noise=self._is_noise_text(f"{title} {digest}"),
                    capture_status="success",
                    failure_reason="ths-news fallback",
                )
            )

        return rows

    def _collect_jin10_weibo_snapshot(
        self, symbol: str, trade_date: date, source_page: str
    ) -> List[Dict[str, str]]:
        try:
            import akshare as ak
        except ImportError:
            return []

        _, name, _ = self._symbol_keywords(symbol)
        try:
            report = ak.stock_js_weibo_report(time_period="CNHOUR12")
        except Exception:
            return []

        if report.empty or "name" not in report.columns:
            return []

        hit = report[report["name"].astype(str).str.contains(name, na=False)]
        if hit.empty:
            return []

        row = hit.iloc[0]
        rate = float(row.get("rate", 0.0))
        text = f"金十数据微博舆情：{name} 近12小时讨论热度指数 {rate:.2f}%"
        return [
            self._build_raw_row(
                trade_date=trade_date,
                platform="weibo",
                symbol=symbol,
                title=f"{name} 微博舆情热度 {rate:.2f}%",
                summary=text,
                post_time=trade_date.isoformat(),
                content=text,
                url="https://datacenter.jin10.com/market",
                source_page=source_page,
                is_noise=False,
                capture_status="success",
                failure_reason="",
            )
        ]

    def _matches_platform_result(
        self,
        platform: str,
        title: str,
        stock_code: str,
        name: str,
        full_text: str,
    ) -> bool:
        blob = f"{title} {full_text}".lower()
        if stock_code in blob or name in blob:
            pass
        elif platform in {"weibo", "xueqiu", "douyin"}:
            return False

        if platform == "weibo":
            return any(token in blob for token in ("微博", "weibo.com", "weibo"))
        if platform == "xueqiu":
            return any(token in blob for token in ("雪球", "xueqiu.com", "xueqiu"))
        if platform == "douyin":
            return any(token in blob for token in ("抖音", "douyin.com", "douyin"))
        return True

    def _dedupe_rows(
        self, rows: List[Dict[str, str]], max_posts: int
    ) -> List[Dict[str, str]]:
        deduped: List[Dict[str, str]] = []
        seen: set[str] = set()
        for row in rows:
            key = str(row.get("title", ""))[:120]
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(row)
            if len(deduped) >= max_posts:
                break
        return deduped

    def _collect_douyin_rows(
        self,
        list_url: str,
        html: str,
        platform: str,
        symbol: str,
        trade_date: date,
        max_posts: int,
    ) -> List[Dict[str, str]]:
        stock_code, name, market_code = self._symbol_keywords(symbol)
        rows = self._collect_web_search_rows(
            platform=platform,
            symbol=symbol,
            trade_date=trade_date,
            queries=[
                f"{stock_code} 抖音",
                f"{name} 抖音",
                f"{market_code} 抖音",
            ],
            max_posts=max_posts,
            source_page=list_url,
        )
        if len(rows) < max_posts:
            rows.extend(
                self._collect_ths_news_rows(
                    platform=platform,
                    symbol=symbol,
                    trade_date=trade_date,
                    max_posts=max_posts,
                    source_page=list_url,
                    keyword_filter="抖音",
                )
            )
        if rows:
            return self._dedupe_rows(rows, max_posts)

        if self._is_waf_page(html):
            return []

        soup = BeautifulSoup(html, "lxml")
        rows = []

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                import json

                payload = json.loads(self._clean_text(script.string or ""))
                items = payload if isinstance(payload, list) else [payload]
                for item in items:
                    title = item.get("headline") or item.get("name") or ""
                    desc = item.get("description") or ""
                    if not title and not desc:
                        continue
                    rows.append(
                        self._build_raw_row(
                            trade_date=trade_date,
                            platform=platform,
                            symbol=symbol,
                            title=title or desc[:120],
                            summary=(desc[:300] if desc else title[:300]),
                            post_time=self._extract_time(
                                desc or title, trade_date=trade_date
                            )
                            or trade_date.isoformat(),
                            content=desc or title,
                            url=list_url,
                            source_page=list_url,
                            is_noise=self._is_noise_text(f"{title} {desc}"),
                            capture_status="success",
                            failure_reason="",
                        )
                    )
                    if len(rows) >= max_posts:
                        return rows
            except Exception:
                continue

        og_title = soup.select_one('meta[property="og:title"]')
        og_desc = soup.select_one('meta[property="og:description"]')
        title = og_title.get("content", "") if og_title else ""
        desc = og_desc.get("content", "") if og_desc else ""
        if title or desc:
            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform=platform,
                    symbol=symbol,
                    title=self._short_title(title or desc or ""),
                    summary=(desc or title or "")[:300],
                    post_time=self._extract_time(desc or title or "", trade_date=trade_date)
                    or trade_date.isoformat(),
                    content=desc or title or "",
                    url=list_url,
                    source_page=list_url,
                    is_noise=self._is_noise_text(f"{title} {desc}"),
                    capture_status="success",
                    failure_reason="",
                )
            )

        return self._dedupe_rows(rows, max_posts)

    def _parse_article_page(
        self,
        platform: str,
        symbol: str,
        trade_date: date,
        page_url: str,
        article_url: str,
        html: str,
        list_title_fallback: str = "",
        post_time_hint: str = "",
    ) -> Dict[str, str]:
        soup = BeautifulSoup(html, "lxml")
        page_title = self._extract_page_title(soup)
        if self._is_guba_blocked_title(page_title) and list_title_fallback:
            page_title = list_title_fallback

        embedded_title, embedded_content = self._extract_guba_embedded_fields(html)
        if embedded_title and not self._is_guba_blocked_title(embedded_title):
            page_title = embedded_title

        text = self._clean_text(soup.get_text(" ", strip=True))

        content_candidate = embedded_content
        if content_candidate:
            content_candidate = strip_boilerplate(content_candidate) or content_candidate

        for sel in (
            "div.newstext",
            "div#zwcon",
            "div.article-content",
            "div#article",
            "div.article",
            "div#content",
            "div.main-content",
            "div.content",
        ):
            if content_candidate and len(content_candidate) >= 120:
                break
            node = soup.select_one(sel)
            if not node:
                continue
            candidate = strip_boilerplate(
                self._clean_text(node.get_text(" ", strip=True))
            ) or self._clean_text(node.get_text(" ", strip=True))
            min_len = 20 if sel == "div.newstext" else 160
            if len(candidate) >= min_len:
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
                if len(best) >= 160:
                    content_candidate = best

        content = (
            content_candidate
            or self._extract_article_content(text)
            or self._normalize_content(text)
        )
        content = strip_boilerplate(content) or strip_boilerplate(page_title) or content

        title = self._short_title(
            list_title_fallback or page_title or embedded_title or content or text
        )
        title = strip_boilerplate(title) or title
        if self._is_guba_blocked_title(title) and list_title_fallback:
            title = self._short_title(list_title_fallback)
        post_time = (
            self._extract_time(text, trade_date=trade_date)
            or post_time_hint
            or trade_date.isoformat()
        )

        if len(content) < 120:
            if list_title_fallback and self._is_valid_guba_list_title(list_title_fallback):
                return self._build_guba_title_row(
                    platform=platform,
                    symbol=symbol,
                    trade_date=trade_date,
                    list_title=list_title_fallback,
                    post_time=post_time,
                    article_url=article_url,
                    page_url=page_url,
                    failure_reason="title_only",
                )
            return {
                **self._build_raw_row(
                    trade_date=trade_date,
                    platform=platform,
                    symbol=symbol,
                    title=self._short_title(page_title or text[:120]),
                    summary="",
                    post_time=post_time,
                    content="",
                    url=article_url,
                    source_page=page_url,
                    is_noise=True,
                    capture_status="fallback",
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
            _, name, _ = self._symbol_keywords(symbol)
            return f"https://s.weibo.com/weibo?q={quote(name)}"
        if platform == "xueqiu":
            return f"https://xueqiu.com/S/{self._to_xueqiu_symbol(symbol)}"
        if platform == "douyin":
            _, name, _ = self._symbol_keywords(symbol)
            return f"https://www.douyin.com/search/{quote(name)}"

        raise ValueError(f"Unsupported platform: {platform}")

    def _download_html(self, url: str, referer: str = "") -> str:
        headers = dict(self._HEADERS)
        if referer:
            headers["Referer"] = referer
        elif "guba.eastmoney.com" in url:
            headers["Referer"] = "https://guba.eastmoney.com/"
        response = requests.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
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
        try:
            if getattr(self, "ai_analyzer", None):
                scores = self.ai_analyzer.score_texts([text])
                if scores:
                    return float(scores[0])
        except Exception:
            pass

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

        # compute keyword score
        pos = sum((title + " " + content).count(word) for word in self._POSITIVE_WORDS)
        neg = sum((title + " " + content).count(word) for word in self._NEGATIVE_WORDS)
        keyword_score = (pos - neg) / (pos + neg + 5) if (pos + neg + 5) != 0 else 0.0

        # Row-level OpenClaw calls are disabled by default: each post would
        # trigger a ~2min LLM round-trip (100+ calls per realtime cycle).
        # Aggregated sentiment in fetch() -> _score_text() is sufficient.
        ai_score = ""
        skip_row_ai = os.environ.get("OPENCLAW_SKIP_ROW_SCORE", "1").lower() in (
            "1",
            "true",
            "yes",
        )
        try:
            if (
                not skip_row_ai
                and getattr(self, "ai_analyzer", None)
                and getattr(self.ai_analyzer, "openclaw", None)
                and self.ai_analyzer.openclaw.is_configured()
            ):
                scores = self.ai_analyzer.score_texts([f"{title} {content}"])
                ai_score = scores[0] if scores else ""
        except Exception:
            ai_score = ""
        if ai_score == "":
            ai_score = float(keyword_score)

        score_source = "keyword"
        if (
            not skip_row_ai
            and ai_score != ""
            and abs(float(ai_score) - float(keyword_score)) > 0.0001
        ):
            score_source = "openclaw"

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

    def _apply_batch_ai_scores(self, rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Batch-score collected rows with OpenClaw (one API call per platform batch)."""
        skip_row_ai = os.environ.get("OPENCLAW_SKIP_ROW_SCORE", "1").lower() in (
            "1",
            "true",
            "yes",
        )
        if skip_row_ai or not getattr(self, "ai_analyzer", None):
            for row in rows:
                row.setdefault("score_source", "keyword")
            return rows

        openclaw = getattr(self.ai_analyzer, "openclaw", None)
        if not openclaw or not openclaw.is_configured():
            for row in rows:
                row.setdefault("score_source", "keyword")
            return rows

        texts = [
            f"{row.get('title', '')} {row.get('content', '')}".strip() or str(row.get("title", ""))
            for row in rows
        ]
        try:
            scores = self.ai_analyzer.score_texts(texts)
            if scores and len(scores) == len(rows):
                for row, score in zip(rows, scores):
                    row["ai_score"] = float(score)
                    row["score_source"] = "openclaw"
                return rows
        except Exception:
            pass

        for row in rows:
            row.setdefault("score_source", "keyword")
        return rows

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
        if is_news_headline(text):
            return True
        if not is_user_comment(text):
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

    def _to_xueqiu_symbol(self, symbol: str) -> str:
        symbol = symbol.upper()
        if "." not in symbol:
            return symbol
        stock, market = symbol.split(".", maxsplit=1)
        return f"{market}{stock}"
