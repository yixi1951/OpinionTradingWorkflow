import time
import re
import requests
import argparse
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
import sys
try:
    from text_quality import is_boilerplate, pick_comment_text
except ImportError:
    from scripts.text_quality import is_boilerplate, pick_comment_text
try:
    # optional better extractor
    from readability import Document
except Exception:
    Document = None

RAW = Path('data/labels/annotation_bulk_openclaw.csv')
OUT = Path('data/labels/annotation_bulk_enriched_openclaw.csv')
CACHE_DIR = Path('data/raw/html_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def collapse_whitespace(s: str) -> str:
    return re.sub(r"\s+", ' ', s).strip()


def extract_text_from_html(html: str, url: str = '') -> str:
    soup = BeautifulSoup(html, 'lxml')

    if 'guba.eastmoney.com' in str(url):
        for sel in ('div.newstext', 'div#newscontent', 'div.article-body', 'div.stockcodec'):
            node = soup.select_one(sel)
            if node:
                txt = collapse_whitespace(node.get_text(separator=' ', strip=True))
                if len(txt) > 8 and not is_boilerplate(txt):
                    return txt

    # Try common article tags
    article = soup.find('article')
    if article:
        paragraphs = [p.get_text(separator=' ', strip=True) for p in article.find_all('p')]
        txt = ' '.join(paragraphs)
        if len(txt) > 50:
            return collapse_whitespace(txt)

    # Heuristic: find largest div by text length among candidates
    candidates = []
    for tag in soup.find_all(['div', 'section']):
        text = tag.get_text(separator=' ', strip=True)
        if len(text) > 200:
            candidates.append((len(text), text, tag))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return collapse_whitespace(candidates[0][1])

    # Fallback: join all <p>
    # Try readability if available
    if Document is not None:
        try:
            doc = Document(html)
            summary = doc.summary()
            s_soup = BeautifulSoup(summary, 'lxml')
            paragraphs = [p.get_text(separator=' ', strip=True) for p in s_soup.find_all('p')]
            txt = ' '.join(paragraphs)
            if len(txt) > 50:
                return collapse_whitespace(txt)
        except Exception:
            pass
    paragraphs = [p.get_text(separator=' ', strip=True) for p in soup.find_all('p')]
    txt = ' '.join(paragraphs)
    return collapse_whitespace(txt)


def fetch_url(url: str, timeout: int = 10) -> str | None:
    if not url or not isinstance(url, str):
        return None
    try:
        r = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def main(limit: int | None = None, delay: float = 0.5):
    if not RAW.exists():
        print('Input not found:', RAW)
        return
    df = pd.read_csv(RAW)
    if 'text' not in df.columns:
        df['text'] = ''

    rows = list(df.itertuples(index=False))
    total = len(rows)
    to_process = []
    for i, row in enumerate(rows):
        url = getattr(row, 'url', None) if 'url' in df.columns else None
        text = getattr(row, 'text', '')
        short = isinstance(text, str) and len(str(text).strip()) >= 80
        if url and not short:
            to_process.append((i, url))
    if limit:
        to_process = to_process[:limit]

    print(f'Total rows {total}, will fetch {len(to_process)} urls')

    for idx, url in to_process:
        cache_file = CACHE_DIR / (str(idx) + '.html')
        html = None
        if cache_file.exists():
            try:
                html = cache_file.read_text(encoding='utf-8')
            except Exception:
                html = None
        if html is None:
            html = fetch_url(url)
            if html:
                try:
                    cache_file.write_text(html, encoding='utf-8')
                except Exception:
                    pass
        if not html:
            print(f'[{idx}] fetch failed: {url}')
            continue
        text = extract_text_from_html(html, url=url)
        if text and len(text) > 30 and not is_boilerplate(text):
            df.at[idx, 'text'] = text
            print(f'[{idx}] extracted text ({len(text)} chars)')
        else:
            title = df.at[idx, 'title'] if 'title' in df.columns else ''
            content = df.at[idx, 'content'] if 'content' in df.columns else ''
            fallback = pick_comment_text(text or '', title=str(title or ''), content=str(content or ''))
            if fallback and not is_boilerplate(fallback):
                df.at[idx, 'text'] = fallback
                print(f'[{idx}] fallback to title/content ({len(fallback)} chars)')
            else:
                print(f'[{idx}] no good text extracted')
        time.sleep(delay)

    df.to_csv(OUT, index=False, encoding='utf-8-sig')
    # also write a copy that replaces the auto-label input so downstream picks it up
    alt = Path('data/labels/annotation_bulk_openclaw.csv')
    df.to_csv(alt, index=False, encoding='utf-8-sig')
    print('Wrote', OUT, 'and updated', alt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None, help='Limit number of URLs to fetch')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between requests')
    args = parser.parse_args()
    main(limit=args.limit, delay=args.delay)
