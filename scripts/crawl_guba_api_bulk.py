"""Bulk-crawl 东方财富股吧 via JSON API into data/raw (rebucketed by post date).

Uses gbapi.eastmoney.com Articlelist — paginates far deeper than HTML list pages.
Writes keyword-scored rows with real post_publish_time; trade_date = post calendar day.

Usage:
  PYTHONPATH=src python scripts/crawl_guba_api_bulk.py --max-pages 40 --delay 0.35
  PYTHONPATH=src python scripts/crawl_guba_api_bulk.py --symbols 600519.SH,000858.SZ --max-pages 10
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from opinion_trading.core.raw_store import RawPostCsvStore  # noqa: E402
from text_quality import is_boilerplate, is_news_headline, is_user_comment  # noqa: E402

DEFAULT_CONFIG = ROOT / "config" / "settings.yaml"
API_URL = "https://gbapi.eastmoney.com/webarticlelist/api/Article/Articlelist"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://guba.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Extra liquid names beyond settings.yaml for wider FM cross-section.
EXTRA_SYMBOLS = [
    "600000.SH",
    "600016.SH",
    "600028.SH",
    "600031.SH",
    "600048.SH",
    "600050.SH",
    "600104.SH",
    "600196.SH",
    "600309.SH",
    "600406.SH",
    "600438.SH",
    "600547.SH",
    "600570.SH",
    "600585.SH",
    "600690.SH",
    "600703.SH",
    "600745.SH",
    "600809.SH",
    "600893.SH",
    "601088.SH",
    "601288.SH",
    "601328.SH",
    "601398.SH",
    "601601.SH",
    "601628.SH",
    "601668.SH",
    "601688.SH",
    "601766.SH",
    "601857.SH",
    "601888.SH",
    "601899.SH",
    "601919.SH",
    "603259.SH",
    "603288.SH",
    "603501.SH",
    "000002.SZ",
    "000063.SZ",
    "000166.SZ",
    "000338.SZ",
    "000725.SZ",
    "000776.SZ",
    "000895.SZ",
    "000938.SZ",
    "002027.SZ",
    "002142.SZ",
    "002230.SZ",
    "002352.SZ",
    "002460.SZ",
    "002475.SZ",
    "002594.SZ",
    "300015.SZ",
    "300059.SZ",
    "300122.SZ",
    "300124.SZ",
    "300274.SZ",
]


def load_symbols(config_path: Path, *, with_extra: bool) -> List[str]:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    base = list(cfg.get("universe", {}).get("symbols", []))
    if not with_extra:
        return base
    seen: Set[str] = set()
    out: List[str] = []
    for s in base + EXTRA_SYMBOLS:
        u = s.strip().upper()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def stock_code(symbol: str) -> str:
    return symbol.split(".", maxsplit=1)[0]


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def keyword_score(title: str) -> float:
    positive = ("看好", "买入", "加仓", "超预期", "利好", "上涨", "突破", "强势", "涨停", "反弹")
    negative = ("看空", "卖出", "减仓", "利空", "下跌", "暴跌", "风险", "套牢", "跌停", "割肉")
    text = clean_text(title)
    pos = sum(text.count(word) for word in positive)
    neg = sum(text.count(word) for word in negative)
    return (pos - neg) / (pos + neg + 5) if (pos + neg + 5) else 0.0


def title_ok(title: str, *, url: str = "", post_type: int = 0) -> bool:
    t = clean_text(title)
    if len(t) < 4 or len(t) > 200:
        return False
    if is_boilerplate(t):
        return False
    # Soft filter: keep short retail comments; drop obvious news headlines.
    if post_type in (1, 2, 20) and is_news_headline(t, "guba"):
        return False
    if post_type == 0:
        return is_user_comment(t, platform="guba", url=url, title=t) or len(t) >= 6
    return True


def parse_post_time(raw: Any) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    try:
        ts = pd.to_datetime(raw, errors="coerce")
    except Exception:
        return None
    if pd.isna(ts):
        return None
    if hasattr(ts, "to_pydatetime"):
        return ts.to_pydatetime()
    return None


def fetch_page(
    session: requests.Session,
    code: str,
    page: int,
    *,
    page_size: int,
    retries: int = 3,
) -> List[Dict[str, Any]]:
    params = {
        "code": code,
        "p": page,
        "ps": page_size,
        "type": 0,
        "sort": 0,
        "uid": "",
        "deviceid": "1",
        "version": "900",
        "product": "Guba",
        "plat": "Web",
    }
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.get(API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return list(data.get("re") or [])
        except Exception as exc:
            last_exc = exc
            time.sleep(1.2 * (attempt + 1))
    if last_exc:
        print(f"  page {page} failed: {last_exc}")
    return []


def item_to_row(item: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
    title = clean_text(item.get("post_title"))
    post_id = item.get("post_id")
    if not title or not post_id:
        return None
    post_type = int(item.get("post_type") or 0)
    url = clean_text(item.get("art_unique_url")) or (
        f"https://guba.eastmoney.com/news,{stock_code(symbol)},{post_id}.html"
    )
    if not title_ok(title, url=url, post_type=post_type):
        return None
    dt = parse_post_time(item.get("post_publish_time")) or parse_post_time(
        item.get("post_display_time")
    )
    if dt is None:
        return None
    trade_date = dt.date().isoformat()
    post_time = dt.strftime("%Y-%m-%d %H:%M:%S")
    score = keyword_score(title)
    summary = title[:180]
    return {
        "trade_date": trade_date,
        "platform": "guba",
        "symbol": symbol,
        "title": title[:120],
        "summary": summary,
        "post_time": post_time,
        "content": title,
        "url": url,
        "source_page": API_URL,
        "fetch_time": datetime.now().isoformat(timespec="seconds"),
        "is_noise": False,
        "capture_status": "success",
        "failure_reason": "",
        "keyword_score": score,
        "ai_score": score,
        "score_source": "keyword",
        "post_id": str(post_id),
        "post_type": post_type,
        "post_click_count": item.get("post_click_count", ""),
        "post_comment_count": item.get("post_comment_count", ""),
        "user_nickname": clean_text(item.get("user_nickname")),
    }


def load_existing_urls(raw_dir: Path) -> Set[str]:
    urls: Set[str] = set()
    for path in raw_dir.glob("raw_posts_*.csv"):
        try:
            df = pd.read_csv(path, usecols=lambda c: c in {"url", "post_id"})
        except Exception:
            continue
        if "url" in df.columns:
            urls |= {str(u).strip() for u in df["url"].dropna()}
    by_source = raw_dir / "by_source"
    if by_source.is_dir():
        for path in by_source.glob("*_guba.csv"):
            try:
                df = pd.read_csv(path, usecols=lambda c: c in {"url"})
            except Exception:
                continue
            if "url" in df.columns:
                urls |= {str(u).strip() for u in df["url"].dropna()}
    return urls


def merge_rows_by_date(raw_dir: Path, rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """Merge rows into raw_posts_YYYY-MM-DD.csv keyed by post calendar day."""
    store = RawPostCsvStore(str(raw_dir))
    by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[str(row["trade_date"])].append(row)

    written: Dict[str, int] = {}
    for trade_date, group in sorted(by_date.items()):
        path = raw_dir / f"raw_posts_{trade_date}.csv"
        existing: List[Dict[str, Any]] = []
        if path.exists():
            try:
                existing = pd.read_csv(path).to_dict(orient="records")
            except Exception:
                existing = []
        existing_urls = {str(r.get("url") or "").strip() for r in existing}
        new_rows = [r for r in group if str(r.get("url") or "").strip() not in existing_urls]
        if not new_rows and existing:
            written[trade_date] = 0
            continue
        combined = existing + new_rows
        store.save_partitioned_rows(trade_date, combined)
        written[trade_date] = len(new_rows)
    return written


def crawl_symbol(
    session: requests.Session,
    symbol: str,
    *,
    max_pages: int,
    page_size: int,
    delay: float,
    existing_urls: Set[str],
    stop_before: Optional[date],
) -> List[Dict[str, Any]]:
    code = stock_code(symbol)
    rows: List[Dict[str, Any]] = []
    seen_local: Set[str] = set()
    for page in range(1, max_pages + 1):
        items = fetch_page(session, code, page, page_size=page_size)
        if not items:
            print(f"  {symbol} page {page}: empty — stop")
            break
        added = 0
        oldest: Optional[date] = None
        for item in items:
            row = item_to_row(item, symbol)
            if row is None:
                continue
            url = str(row["url"])
            if url in existing_urls or url in seen_local:
                continue
            seen_local.add(url)
            rows.append(row)
            added += 1
            pt = parse_post_time(row["post_time"])
            if pt is not None:
                d = pt.date()
                if oldest is None or d < oldest:
                    oldest = d
        print(
            f"  {symbol} page {page}: +{added} kept "
            f"(page_items={len(items)}, oldest={oldest})"
        )
        if stop_before is not None and oldest is not None and oldest < stop_before:
            print(f"  {symbol}: reached stop_before={stop_before.isoformat()} — stop")
            break
        time.sleep(delay)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk crawl guba via JSON API")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG))
    parser.add_argument("--symbols", type=str, default="")
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--page-size", type=int, default=80)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--raw-dir", type=str, default=str(ROOT / "data" / "raw"))
    parser.add_argument(
        "--with-extra-symbols",
        action="store_true",
        help="Append EXTRA_SYMBOLS for wider cross-section",
    )
    parser.add_argument(
        "--stop-before",
        type=str,
        default="",
        help="Stop a symbol once oldest post on a page is before this YYYY-MM-DD",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.symbols.strip():
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = load_symbols(Path(args.config), with_extra=args.with_extra_symbols)

    stop_before = date.fromisoformat(args.stop_before) if args.stop_before else None
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    existing = load_existing_urls(raw_dir)
    print(f"Symbols: {len(symbols)} | existing URLs: {len(existing)}")
    print(f"max_pages={args.max_pages} page_size={args.page_size} delay={args.delay}")

    session = requests.Session()
    session.headers.update(HEADERS)

    all_rows: List[Dict[str, Any]] = []
    t0 = time.time()
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] Crawling {symbol} ...")
        rows = crawl_symbol(
            session,
            symbol,
            max_pages=args.max_pages,
            page_size=args.page_size,
            delay=args.delay,
            existing_urls=existing,
            stop_before=stop_before,
        )
        all_rows.extend(rows)
        for r in rows:
            existing.add(str(r["url"]))
        print(f"  -> {len(rows)} new rows for {symbol} (running total {len(all_rows)})")

    elapsed = time.time() - t0
    print(f"Collected {len(all_rows)} new rows in {elapsed:.1f}s")
    if not all_rows:
        print("Nothing to write.")
        return
    if args.dry_run:
        by_sym = pd.DataFrame(all_rows).groupby("symbol").size()
        by_day = pd.DataFrame(all_rows).groupby("trade_date").size()
        print("by_symbol:\n", by_sym.to_string())
        print("by_date span:", by_day.index.min(), "->", by_day.index.max(), "days", len(by_day))
        return

    written = merge_rows_by_date(raw_dir, all_rows)
    new_total = sum(written.values())
    print(f"Merged into {len(written)} daily files (+{new_total} new rows)")
    dates = sorted(written.keys())
    if dates:
        print(f"Date span: {dates[0]} -> {dates[-1]}")


if __name__ == "__main__":
    main()
