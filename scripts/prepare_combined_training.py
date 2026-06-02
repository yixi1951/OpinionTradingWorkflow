"""Merge sample + bulk human labels into one training CSV.

Sample text comes from annotation_sample.csv (raw/by_source title/content).
Legacy merged files with sentiment log lines are ignored when sample.csv exists.

Usage:
  py scripts/prepare_combined_training.py
  py scripts/prepare_combined_training.py --include-weak-bulk
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from text_quality import is_log_metadata, pick_comment_text, quality_issues

LABEL_DIR = Path('data/labels')
RAW_DIR = Path('data/raw')

HARD_REJECT = {'stock_or_search_url', 'boilerplate', 'mojibake', 'too_short', 'news_article', 'news_headline'}


def extract_url(text: str) -> str:
    m = re.search(r'https?://[^\s,"]+', str(text))
    if not m:
        return ''
    return m.group(0).replace('list,', 'list/')


def load_raw_posts() -> pd.DataFrame:
    parts = []
    for f in RAW_DIR.glob('**/*.csv'):
        try:
            parts.append(pd.read_csv(f))
        except Exception:
            pass
    if not parts:
        return pd.DataFrame()
    raw = pd.concat(parts, ignore_index=True)
    if 'url' in raw.columns:
        raw['url'] = raw['url'].astype(str).str.strip()
    return raw


def resolve_sample_text(row, bulk_by_url: dict, raw_by_url: dict) -> str:
    url = extract_url(row.get('text', ''))
    if url and url in bulk_by_url:
        b = bulk_by_url[url]
        return pick_comment_text(
            str(b.get('text', '') or ''),
            title=str(b.get('title', '') or ''),
            content=str(b.get('content', '') or ''),
            summary=str(b.get('summary', '') or ''),
        )
    if url and url in raw_by_url:
        r = raw_by_url[url]
        return pick_comment_text(
            '',
            title=str(r.get('title', '') or ''),
            content=str(r.get('content', '') or ''),
            summary=str(r.get('summary', '') or ''),
        )
    return ''


def load_bulk_training(include_weak: bool) -> pd.DataFrame:
    src = LABEL_DIR / 'annotation_bulk_review_merged.csv'
    if not src.exists():
        raise SystemExit(f'Missing {src}')
    df = pd.read_csv(src)
    label_col = 'label_review' if 'label_review' in df.columns else 'label'
    rows = []
    for _, row in df.iterrows():
        if pd.isna(row.get(label_col)) or str(row.get(label_col)).strip() == '':
            continue
        text = pick_comment_text(
            str(row.get('text', '') or ''),
            title=str(row.get('title', '') or ''),
            content=str(row.get('content', '') or ''),
            summary=str(row.get('summary', '') or ''),
        )
        issues = quality_issues(
            str(row.get('text', '') or ''),
            title=str(row.get('title', '') or ''),
            platform=str(row.get('platform', '') or ''),
            url=str(row.get('url', '') or ''),
        )
        hard = [i for i in issues if i in HARD_REJECT]
        weak = [i for i in issues if i not in HARD_REJECT]
        tier = 'reject' if hard else ('weak' if weak else 'good')
        if tier == 'reject':
            continue
        if tier == 'weak' and not include_weak:
            continue
        rows.append({'text': text, 'label': str(row[label_col]).strip(), 'source': 'bulk'})
    return pd.DataFrame(rows)


def _sample_text_from_row(row) -> str:
    text = pick_comment_text(
        str(row.get('text', '') or ''),
        title=str(row.get('title', '') or ''),
        content=str(row.get('content', '') or ''),
        summary=str(row.get('summary', '') or ''),
    )
    if text and not is_log_metadata(text):
        return text
    url = str(row.get('url', '') or extract_url(row.get('text', ''))).strip()
    return ''


def load_sample_training(bulk_by_url: dict, raw_by_url: dict) -> pd.DataFrame:
    review = LABEL_DIR / 'annotation_sample_review.csv'
    sample_csv = LABEL_DIR / 'annotation_sample.csv'
    rows = []

    if sample_csv.exists() and review.exists():
        samp = pd.read_csv(sample_csv)
        rev = pd.read_csv(review)
        joined = samp.merge(rev[['id', 'label']], on='id', how='inner', suffixes=('', '_human'))
        for _, row in joined.iterrows():
            label = str(row.get('label_human', row.get('label', ''))).strip()
            if not label:
                continue
            text = _sample_text_from_row(row)
            if not text:
                url = str(row.get('url', '') or '').strip()
                if url and url in bulk_by_url:
                    text = _sample_text_from_row(bulk_by_url[url])
                elif url and url in raw_by_url:
                    text = pick_comment_text(
                        '',
                        title=str(raw_by_url[url].get('title', '') or ''),
                        content=str(raw_by_url[url].get('content', '') or ''),
                        summary=str(raw_by_url[url].get('summary', '') or ''),
                    )
            if not text or is_log_metadata(text):
                continue
            url = str(row.get('url', '') or extract_url(row.get('text', '')))
            issues = quality_issues(
                text,
                platform=str(row.get('platform', '') or ''),
                url=url,
            )
            if any(i in HARD_REJECT for i in issues):
                continue
            rows.append({'text': text, 'label': label, 'source': 'sample'})
        if rows:
            return pd.DataFrame(rows)

    merged = LABEL_DIR / 'annotation_sample_review_merged.csv'
    if not review.exists() or not merged.exists():
        return pd.DataFrame(columns=['text', 'label', 'source'])
    rev = pd.read_csv(review)
    samp = pd.read_csv(merged)
    samp = samp.merge(rev[['id', 'label']], on='id', how='inner', suffixes=('', '_human'))
    for _, row in samp.iterrows():
        label = str(row.get('label_human', row.get('label_review', row.get('label', '')))).strip()
        if not label:
            continue
        text = resolve_sample_text(row, bulk_by_url, raw_by_url)
        if not text or is_log_metadata(text):
            continue
        issues = quality_issues(
            text,
            platform=str(row.get('platform', '') or ''),
            url=extract_url(row.get('text', '')),
        )
        if any(i in HARD_REJECT for i in issues):
            continue
        rows.append({'text': text, 'label': label, 'source': 'sample'})
    return pd.DataFrame(rows)


def main(include_weak_bulk: bool = True):
    bulk_src = LABEL_DIR / 'annotation_bulk_review_merged.csv'
    bulk_df = pd.read_csv(bulk_src) if bulk_src.exists() else pd.DataFrame()
    bulk_by_url = {}
    if not bulk_df.empty and 'url' in bulk_df.columns:
        for _, r in bulk_df.iterrows():
            u = str(r.get('url', '') or '').strip()
            if u:
                bulk_by_url[u] = r

    raw = load_raw_posts()
    raw_by_url = {}
    if not raw.empty and 'url' in raw.columns:
        for _, r in raw.iterrows():
            u = str(r.get('url', '') or '').strip()
            if u and u not in raw_by_url:
                raw_by_url[u] = r

    bulk_part = load_bulk_training(include_weak_bulk)
    sample_part = load_sample_training(bulk_by_url, raw_by_url)

    combined = pd.concat([sample_part, bulk_part], ignore_index=True)
    combined = combined.drop_duplicates(subset=['text', 'label']).reset_index(drop=True)

    out = LABEL_DIR / 'annotation_combined_for_training.csv'
    meta = LABEL_DIR / 'annotation_combined_meta.csv'
    combined[['text', 'label']].to_csv(out, index=False, encoding='utf-8-sig')
    combined.to_csv(meta, index=False, encoding='utf-8-sig')

    print('Combined training set:')
    print(f'  sample rows: {len(sample_part)}')
    print(f'  bulk rows:   {len(bulk_part)}')
    print(f'  total (dedup): {len(combined)}')
    print('\nLabel distribution:')
    print(combined['label'].value_counts().to_string())
    print('\nBy source:')
    print(combined.groupby(['source', 'label']).size().to_string())
    print(f'\nWrote {out}')
    print(f'Wrote {meta}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--strict-bulk', action='store_true', help='Exclude weak bulk rows (title-only)')
    args = parser.parse_args()
    main(include_weak_bulk=not args.strict_bulk)
