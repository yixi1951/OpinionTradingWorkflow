"""从 raw/by_source 抽取可标注评论样本（title/content，非 sentiment 日志）

用法示例：
  python scripts/sample_annotation.py --n 100 --seed 42
  python scripts/sample_annotation.py --n 100 --platforms guba --migrate-review

输出：data/labels/annotation_sample.csv
"""
import argparse
import re
from pathlib import Path

import pandas as pd

from raw_sampling import RAW_BY_SOURCE, sample_posts, to_annotation_frame
from review_export import export_review_merged

DEFAULT_OUT = Path('data/labels/annotation_sample.csv')
REVIEW_PATH = Path('data/labels/annotation_sample_review.csv')
OLD_MERGED = Path('data/labels/annotation_sample_review_merged.csv')


def extract_url(text: str) -> str:
    m = re.search(r'https?://[^\s,"]+', str(text))
    if not m:
        return ''
    return m.group(0).replace('list,', 'list/')


def migrate_review_labels(new_sample: pd.DataFrame) -> int:
    """Map review labels onto new sample rows by URL (from old sample or bulk review)."""
    url_labels: dict[str, dict] = {}

    bulk_merged = Path('data/labels/annotation_bulk_review_merged.csv')
    if bulk_merged.exists():
        bm = pd.read_csv(bulk_merged)
        if 'label_review' in bm.columns and 'url' in bm.columns:
            for _, row in bm.iterrows():
                lab = row.get('label_review')
                u = str(row.get('url', '') or '').strip()
                if u and not pd.isna(lab) and str(lab).strip():
                    url_labels[u] = {
                        'label': str(lab).strip(),
                        'notes': row.get('notes', ''),
                        'annotator': row.get('annotator', 'annotator1'),
                    }

    if OLD_MERGED.exists():
        old = pd.read_csv(OLD_MERGED)
        label_col = 'label_review' if 'label_review' in old.columns else 'label'
        for _, row in old.iterrows():
            lab = row.get(label_col)
            if pd.isna(lab) or not str(lab).strip():
                continue
            u = extract_url(row.get('text', ''))
            if u and u not in url_labels:
                url_labels[u] = {
                    'label': str(lab).strip(),
                    'notes': row.get('notes', ''),
                    'annotator': row.get('annotator', 'annotator1'),
                }

    if REVIEW_PATH.exists() and OLD_MERGED.exists():
        rev = pd.read_csv(REVIEW_PATH)
        merged_old = pd.read_csv(OLD_MERGED)
        for _, r in rev.iterrows():
            lab = r.get('label')
            if pd.isna(lab):
                continue
            hit = merged_old[merged_old['id'] == r['id']]
            if hit.empty:
                continue
            u = extract_url(hit.iloc[0]['text'])
            if u and u not in url_labels:
                url_labels[u] = {
                    'label': str(lab).strip(),
                    'notes': r.get('notes', ''),
                    'annotator': r.get('annotator', 'annotator1'),
                }

    rows = []
    for _, row in new_sample.iterrows():
        u = str(row.get('url', '') or '').strip()
        if u in url_labels:
            rows.append({'id': int(row['id']), **url_labels[u]})
    if not rows:
        return 0
    out = pd.DataFrame(rows)
    out.to_csv(REVIEW_PATH, index=False, encoding='utf-8-sig')
    return len(out)


def main(
    n: int,
    seed: int,
    out: str,
    platforms: str,
    migrate_review: bool,
    exclude_bulk: bool = False,
):
    exclude_urls: set[str] = set()
    bulk_path = Path('data/labels/annotation_bulk.csv')
    if exclude_bulk and bulk_path.exists():
        b = pd.read_csv(bulk_path)
        if 'url' in b.columns:
            exclude_urls = set(b['url'].astype(str))

    plat_list = [p.strip() for p in platforms.split(',') if p.strip()]
    sampled = sample_posts(
        n=n,
        seed=seed,
        platforms=plat_list,
        exclude_urls=exclude_urls or None,
        only_by_source=True,
    )
    if sampled.empty:
        print(f'No rows found under {RAW_BY_SOURCE} for platforms={platforms}')
        return

    out_df = to_annotation_frame(sampled, start_id=1)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f'Wrote {len(out_df)} rows to {out_path} (from {RAW_BY_SOURCE})')

    if migrate_review:
        n_migrated = migrate_review_labels(out_df)
        print(f'Migrated {n_migrated} review labels to {REVIEW_PATH} (matched by url)')
    n_exp = export_review_merged(out_path, REVIEW_PATH, OLD_MERGED)
    if n_exp:
        print(f'Exported {n_exp} labeled rows to {OLD_MERGED}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--out', type=str, default=str(DEFAULT_OUT))
    parser.add_argument('--platforms', type=str, default='guba', help='e.g. guba or guba,weibo')
    parser.add_argument('--migrate-review', action='store_true', help='Restore labels from old review by URL')
    parser.add_argument('--exclude-bulk', action='store_true', help='Skip URLs already in annotation_bulk.csv')
    args = parser.parse_args()
    main(args.n, args.seed, args.out, args.platforms, args.migrate_review, args.exclude_bulk)
