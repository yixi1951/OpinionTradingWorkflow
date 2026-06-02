"""Crawl guba (东方财富股吧) posts into data/raw/by_source.

List-page anchor text is used as title (short user comments). Skips URLs
already present in by_source/*_guba.csv.

Usage:
  py scripts/crawl_guba_raw.py
  py scripts/crawl_guba_raw.py --max-pages 15 --delay 0.3
  py scripts/crawl_guba_raw.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from opinion_trading.core.raw_store import RawPostCsvStore
from text_quality import is_boilerplate, is_news_headline

BY_SOURCE = ROOT / "data" / "raw" / "by_source"
DEFAULT_CONFIG = ROOT / "config" / "settings.yaml"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def load_symbols(config_path: Path) -> list[str]:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return list(cfg.get("universe", {}).get("symbols", []))


def load_existing_urls() -> set[str]:
    urls: set[str] = set()
    if not BY_SOURCE.exists():
        return urls
    for path in BY_SOURCE.glob("*_guba.csv"):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "url" in df.columns:
            urls |= {str(u).strip() for u in df["url"].dropna()}
    return urls


def to_list_code(symbol: str) -> tuple[str, str]:
    stock, market = symbol.upper().split(".", maxsplit=1)
    list_code = f"{'sh' if market == 'SH' else 'sz'}{stock}"
    return stock, list_code


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def title_ok(title: str) -> bool:
    t = clean_text(title)
    if len(t) < 8 or len(t) > 150:
        return False
    if is_boilerplate(t) or is_news_headline(t, "guba"):
        return False
    return True


def fetch_html(url: str, timeout: int = 15) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding or "utf-8"
    return resp.text


def collect_symbol_entries(
    symbol: str,
    max_pages: int,
    delay: float,
) -> list[tuple[str, str]]:
    stock_code, list_code = to_list_code(symbol)
    list_base = f"https://guba.eastmoney.com/list,{list_code}"
    seen_hrefs: set[str] = set()
    entries: list[tuple[str, str]] = []

    for page in range(1, max_pages + 1):
        suffix = "" if page == 1 else f",{page}"
        list_url = f"{list_base}{suffix}.html"
        try:
            html = fetch_html(list_url)
        except Exception as exc:
            print(f"  page {page} failed: {exc}")
            break

        soup = BeautifulSoup(html, "lxml")
        page_count = 0
        for anchor in soup.select('a[href^="/news,"]'):
            href = clean_text(anchor.get("href", ""))
            if not href or f",{stock_code}," not in href:
                continue
            if href in seen_hrefs:
                continue
            title = clean_text(anchor.get_text(" ", strip=True))
            seen_hrefs.add(href)
            entries.append((href, title))
            page_count += 1

        print(f"  {symbol} page {page}: +{page_count} links (total {len(entries)})")
        if page_count == 0:
            break
        time.sleep(delay)

    return entries


def build_row(
    *,
    symbol: str,
    trade_date: str,
    list_url: str,
    href: str,
    title: str,
) -> dict:
    url = urljoin("https://guba.eastmoney.com", href)
    short_title = title[:120]
    return {
        "trade_date": trade_date,
        "platform": "guba",
        "symbol": symbol,
        "title": short_title,
        "summary": short_title[:180],
        "post_time": trade_date,
        "content": short_title,
        "url": url,
        "source_page": list_url,
        "fetch_time": datetime.now().isoformat(),
        "is_noise": False,
        "capture_status": "success",
        "failure_reason": "",
        "keyword_score": "",
        "ai_score": "",
    }


def main(
    symbols: list[str],
    trade_date: str,
    max_pages: int,
    delay: float,
    max_new: int | None,
    dry_run: bool,
) -> None:
    existing = load_existing_urls()
    print(f"Existing guba URLs in by_source: {len(existing)}")

    candidates: list[tuple[str, str, str, str]] = []
    for symbol in symbols:
        print(f"Crawling list pages for {symbol} ...")
        _, list_code = to_list_code(symbol)
        list_url = f"https://guba.eastmoney.com/list,{list_code}.html"
        for href, title in collect_symbol_entries(symbol, max_pages, delay):
            full_url = urljoin("https://guba.eastmoney.com", href)
            if full_url in existing:
                continue
            if not title_ok(title):
                continue
            candidates.append((symbol, list_url, href, title))
        time.sleep(delay)

    print(f"New comment-like candidates: {len(candidates)}")
    if max_new is not None:
        candidates = candidates[:max_new]
        print(f"Truncated to --max-new={max_new}")

    if dry_run:
        by_symbol: dict[str, int] = {}
        for symbol, _, _, _ in candidates:
            by_symbol[symbol] = by_symbol.get(symbol, 0) + 1
        for symbol, count in sorted(by_symbol.items()):
            print(f"  {symbol}: {count}")
        return

    rows = [
        build_row(
            symbol=symbol,
            trade_date=trade_date,
            list_url=list_url,
            href=href,
            title=title,
        )
        for symbol, list_url, href, title in candidates
    ]
    if not rows:
        print("No new rows to write.")
        return

    store = RawPostCsvStore(str(ROOT / "data" / "raw"))
    outputs = store.save_partitioned_rows(trade_date, rows)
    print(f"Wrote {len(rows)} new rows")
    print(f"  combined: {outputs['combined']}")
    print(f"  guba:     {outputs.get('source:guba')}")

    total = 0
    for path in BY_SOURCE.glob("*_guba.csv"):
        try:
            total += len(pd.read_csv(path))
        except Exception:
            pass
    print(f"Total guba rows in by_source now: {total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl guba posts into data/raw/by_source")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG))
    parser.add_argument(
        "--symbols",
        type=str,
        default="",
        help="Comma-separated symbols; default from config/settings.yaml",
    )
    parser.add_argument("--trade-date", type=str, default=date.today().isoformat())
    parser.add_argument("--max-pages", type=int, default=12, help="List pages per symbol")
    parser.add_argument("--delay", type=float, default=0.35, help="Seconds between requests")
    parser.add_argument("--max-new", type=int, default=None, help="Cap total new rows written")
    parser.add_argument("--dry-run", action="store_true", help="Count candidates only")
    args = parser.parse_args()

    if args.symbols.strip():
        symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        symbol_list = load_symbols(Path(args.config))

    main(
        symbols=symbol_list,
        trade_date=args.trade_date,
        max_pages=args.max_pages,
        delay=args.delay,
        max_new=args.max_new,
        dry_run=args.dry_run,
    )
