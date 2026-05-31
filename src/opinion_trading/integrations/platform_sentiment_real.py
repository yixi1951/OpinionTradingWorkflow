from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from opinion_trading.integrations.platform_sentiment_stub import (
    PlatformSentimentProvider as StubProvider,
)
from opinion_trading.core.ai_sentiment import AISentimentAnalyzer


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
        self, platform: str, symbol: str, trade_date: date, max_posts: int = 6
    ) -> List[Dict[str, str]]:
        try:
            list_url = self._build_url(platform=platform, symbol=symbol)
            html = self._download_html(list_url)

            if platform in {"guba", "eastmoney"}:
                rows = self._collect_guba_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )
            elif platform in {"sina_finance"}:
                rows = self._collect_generic_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )
            elif platform in {"douyin"}:
                rows = self._collect_douyin_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )
            else:
                rows = self._collect_generic_rows(
                    list_url, html, platform, symbol, trade_date, max_posts=max_posts
                )

            if rows:
                return rows

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
            article_url = urljoin("https://guba.eastmoney.com", href)
            article_html = self._download_html(article_url)
            row = self._parse_article_page(
                platform=platform,
                symbol=symbol,
                trade_date=trade_date,
                page_url=list_url,
                article_url=article_url,
                html=article_html,
            )
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
                                post_time=self._extract_time(desc or title, trade_date=trade_date),
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
            except Exception:
                continue

        # fallback to og/meta tags
        og_title = (soup.select_one('meta[property="og:title"]') or {}).get("content") if soup.select_one('meta[property="og:title"]') else None
        og_desc = (soup.select_one('meta[property="og:description"]') or {}).get("content") if soup.select_one('meta[property="og:description"]') else None
        if og_title or og_desc:
            rows.append(
                self._build_raw_row(
                    trade_date=trade_date,
                    platform=platform,
                    symbol=symbol,
                    title=self._short_title(og_title or og_desc or ""),
                    summary=(og_desc or og_title or "")[:300],
                    post_time=self._extract_time(og_desc or og_title or "", trade_date=trade_date),
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
        page_title = self._extract_page_title(soup)
        text = self._clean_text(soup.get_text(" ", strip=True))

        # try to extract richer article content using common article containers
        content_candidate = ""
        for sel in (
            "div#zwcon",
            "div.article-content",
            "div#article",
            "div.article",
            "div#content",
            "div.main-content",
            "div.content",
        ):
            node = soup.select_one(sel)
            if node:
                candidate = self._clean_text(node.get_text(" ", strip=True))
                if len(candidate) >= 160:
                    content_candidate = candidate
                    break

        if not content_candidate:
            # fallback to longest block of text in the page
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

        title = self._short_title(page_title or content or text)
        post_time = self._extract_time(text, trade_date=trade_date)

        # if content is too short, treat as parse failure to reduce fallback pollution
        if len(content) < 120:
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
        response = requests.get(url, headers=self._HEADERS, timeout=self.timeout)
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
        return self._clean_text(value)[:800]

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

        # compute ai score if analyzer available
        ai_score = ""
        try:
            if getattr(self, "ai_analyzer", None):
                scores = self.ai_analyzer.score_texts([f"{title} {content}"])
                ai_score = scores[0] if scores else ""
        except Exception:
            ai_score = ""

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
