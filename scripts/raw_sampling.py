"""Load and filter comment-like rows from data/raw/by_source/*.csv."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

try:
    from text_quality import is_boilerplate, is_news_headline, pick_comment_text
except ImportError:
    from scripts.text_quality import is_boilerplate, is_news_headline, pick_comment_text

RAW_BY_SOURCE = Path('data/raw/by_source')
RAW_ROOT = Path('data/raw')

SKIP_URL_FRAGMENTS = (
    'xueqiu.com/S/',
    'realstock/company',
    's.weibo.com/weibo?q=',
    'guba.eastmoney.com/list',
)

NEWS_TITLE_MARKERS = ('资讯', '来源：', '来源:', '概念涨', '证券时报', '北京商报', '蓝鲸财经')


def load_raw_csvs(
    platforms: list[str] | None = None,
    only_by_source: bool = True,
) -> pd.DataFrame:
    base = RAW_BY_SOURCE if only_by_source else RAW_ROOT
    pattern = '**/*.csv' if not only_by_source else '*_*.csv'
    files = list(base.glob(pattern))
    parts = []
    for f in files:
        try:
            parts.append(pd.read_csv(f))
        except Exception:
            continue
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    if platforms:
        wanted = {p.strip().lower() for p in platforms}
        df = df[df['platform'].astype(str).str.lower().isin(wanted)]
    return df


def _url_ok(url: str, platform: str) -> bool:
    u = str(url or '').lower()
    if not u or any(x in u for x in SKIP_URL_FRAGMENTS):
        return False
    if platform == 'guba':
        return 'guba.eastmoney.com/news' in u
    return True


def _title_ok(title: str, platform: str) -> bool:
    t = str(title or '').strip()
    if len(t) < 8 or len(t) > 150:
        return False
    if is_boilerplate(t) or is_news_headline(t, platform):
        return False
    if any(m in t for m in NEWS_TITLE_MARKERS):
        return False
    return True


def filter_comment_rows(df: pd.DataFrame, platform: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    rows = []
    for _, row in df.iterrows():
        plat = str(row.get('platform', '') or '').lower()
        if platform and plat != platform.lower():
            continue
        status = str(row.get('capture_status', '') or '').lower()
        if status in {'fallback', 'failed', 'error'}:
            continue
        url = str(row.get('url', '') or '')
        if not _url_ok(url, plat):
            continue
        title = str(row.get('title', '') or '').strip()
        if plat == 'guba':
            if not _title_ok(title, plat):
                continue
            text = title
        else:
            text = pick_comment_text(
                str(row.get('text', '') or ''),
                title=title,
                content=str(row.get('content', '') or ''),
                summary=str(row.get('summary', '') or ''),
            )
            if len(text) < 8 or is_boilerplate(text) or is_news_headline(text, plat):
                continue
        if not text:
            continue
        out = dict(row)
        out['text'] = text
        rows.append(out)
    return pd.DataFrame(rows)


def sample_posts(
    n: int,
    seed: int = 42,
    platforms: list[str] | None = None,
    exclude_urls: set[str] | None = None,
    only_by_source: bool = True,
) -> pd.DataFrame:
    raw = load_raw_csvs(platforms=platforms, only_by_source=only_by_source)
    plat = platforms[0] if platforms and len(platforms) == 1 else None
    filtered = filter_comment_rows(raw, platform=plat)
    if exclude_urls and 'url' in filtered.columns:
        filtered = filtered[~filtered['url'].astype(str).isin(exclude_urls)]
    if filtered.empty:
        return filtered
    n = min(n, len(filtered))
    return filtered.sample(n=n, random_state=seed).reset_index(drop=True)


def to_annotation_frame(sample: pd.DataFrame, start_id: int = 1) -> pd.DataFrame:
    cols = [c for c in ['trade_date', 'platform', 'symbol', 'text', 'title', 'summary', 'content', 'url'] if c in sample.columns]
    out = sample[cols].copy() if cols else sample[['text']].copy()
    out = out.reset_index(drop=True)
    out.insert(0, 'id', range(start_id, start_id + len(out)))
    out['label'] = ''
    out['notes'] = ''
    return out
