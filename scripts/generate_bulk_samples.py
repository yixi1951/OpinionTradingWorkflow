"""Generate bulk annotation CSV from data/raw/by_source (comment posts)."""
import argparse
from pathlib import Path

import pandas as pd

from raw_sampling import RAW_BY_SOURCE, sample_posts, to_annotation_frame
from review_export import export_review_merged

OUT = Path('data/labels/annotation_bulk.csv')
OPENCLAW_COPY = Path('data/labels/annotation_bulk_openclaw.csv')
BULK_REVIEW = Path('data/labels/annotation_bulk_review.csv')
BULK_MERGED = Path('data/labels/annotation_bulk_review_merged.csv')


def load_reviewed_urls() -> set[str]:
    reviewed: set[str] = set()
    merged = Path('data/labels/annotation_bulk_review_merged.csv')
    if merged.exists():
        df = pd.read_csv(merged)
        if 'url' in df.columns:
            reviewed |= set(df['url'].astype(str))
    return reviewed


def migrate_bulk_review(out_df: pd.DataFrame) -> int:
    if not BULK_MERGED.exists() or 'url' not in out_df.columns:
        return 0
    old = pd.read_csv(BULK_MERGED)
    if 'label_review' not in old.columns or 'url' not in old.columns:
        return 0
    by_url = {
        str(r['url']).strip(): {
            'label': str(r['label_review']).strip(),
            'notes': r.get('notes', ''),
            'annotator': r.get('annotator', 'annotator1'),
        }
        for _, r in old.iterrows()
        if pd.notna(r.get('label_review')) and str(r.get('label_review')).strip()
    }
    rows = []
    for _, row in out_df.iterrows():
        u = str(row.get('url', '') or '').strip()
        if u in by_url:
            rows.append({'id': int(row['id']), **by_url[u]})
    if not rows:
        return 0
    pd.DataFrame(rows).to_csv(BULK_REVIEW, index=False, encoding='utf-8-sig')
    return len(rows)


def main(n=500, seed=42, platforms=None, exclude_reviewed=True, migrate_review=True):
    plat_list = [p.strip() for p in (platforms or 'guba').split(',') if p.strip()]
    exclude = load_reviewed_urls() if exclude_reviewed else None
    sampled = sample_posts(
        n=n,
        seed=seed,
        platforms=plat_list,
        exclude_urls=exclude,
        only_by_source=True,
    )
    if sampled.empty:
        print(f'No comment rows under {RAW_BY_SOURCE} (platforms={platforms})')
        return

    if len(sampled) < n:
        print(f'Note: only {len(sampled)} comment posts available (requested {n})')

    out_df = to_annotation_frame(sampled, start_id=0)
    cols = [c for c in out_df.columns]
    out_df.to_csv(OUT, index=False, encoding='utf-8-sig')
    out_df.to_csv(OPENCLAW_COPY, index=False, encoding='utf-8-sig')
    print(f'Wrote {OUT} ({len(out_df)} rows)')
    print(f'Also wrote {OPENCLAW_COPY} ({len(out_df)} rows)')
    if migrate_review:
        n_m = migrate_bulk_review(out_df)
        if n_m:
            print(f'Migrated {n_m} bulk review labels to {BULK_REVIEW} (by url)')
    n_exp = export_review_merged(OUT, BULK_REVIEW, BULK_MERGED)
    if n_exp:
        print(f'Exported {n_exp} labeled rows to {BULK_MERGED}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=500)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--platforms', type=str, default='guba')
    parser.add_argument('--include-reviewed', action='store_true', help='Allow URLs already human-reviewed')
    parser.add_argument('--no-migrate-review', action='store_true', help='Do not copy labels from bulk_review_merged')
    args = parser.parse_args()
    main(
        n=args.n,
        seed=args.seed,
        platforms=args.platforms,
        exclude_reviewed=not args.include_reviewed,
        migrate_review=not args.no_migrate_review,
    )
