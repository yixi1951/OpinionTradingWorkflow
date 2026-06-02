"""Build a training CSV from bulk human review export, with quality filtering.

Usage:
  python scripts/prepare_bulk_training.py
  python scripts/prepare_bulk_training.py --include-weak
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from text_quality import pick_comment_text, quality_issues

LABEL_ROOT = Path('data/labels')
DEFAULT_SRC = LABEL_ROOT / 'annotation_bulk_review_merged.csv'
OUT_TRAIN = LABEL_ROOT / 'annotation_bulk_for_training.csv'
OUT_REJECT = LABEL_ROOT / 'annotation_bulk_rejected.csv'
OUT_REPORT = LABEL_ROOT / 'annotation_bulk_quality_report.csv'

HARD_REJECT = {'stock_or_search_url', 'boilerplate', 'mojibake', 'too_short', 'news_article', 'news_headline'}


def main(include_weak: bool = False):
    if not DEFAULT_SRC.exists():
        raise SystemExit(f'Missing {DEFAULT_SRC}. Export merged CSV from label_review_app first.')

    df = pd.read_csv(DEFAULT_SRC)
    label_col = 'label_review' if 'label_review' in df.columns else 'label'
    if label_col not in df.columns:
        raise SystemExit('No human label column (label_review or label) found.')

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
        rows.append(
            {
                'id': row.get('id'),
                'platform': row.get('platform'),
                'symbol': row.get('symbol'),
                'text': text,
                'label': str(row.get(label_col)).strip(),
                'quality_tier': tier,
                'quality_issues': ';'.join(issues),
                'url': row.get('url'),
            }
        )

    report = pd.DataFrame(rows)
    report.to_csv(OUT_REPORT, index=False, encoding='utf-8-sig')

    keep_tiers = {'good', 'weak'} if include_weak else {'good'}
    train = report[report['quality_tier'].isin(keep_tiers)][['text', 'label']].copy()
    train = train.drop_duplicates(subset=['text', 'label']).reset_index(drop=True)
    reject = report[~report['quality_tier'].isin(keep_tiers)].copy()

    train.to_csv(OUT_TRAIN, index=False, encoding='utf-8-sig')
    reject.to_csv(OUT_REJECT, index=False, encoding='utf-8-sig')

    print('Quality summary:')
    print(report['quality_tier'].value_counts().to_string())
    print('\nTop issues:')
    issue_counts: dict[str, int] = {}
    for cell in report['quality_issues']:
        for part in str(cell).split(';'):
            if part:
                issue_counts[part] = issue_counts.get(part, 0) + 1
    for k, v in sorted(issue_counts.items(), key=lambda x: -x[1])[:8]:
        print(f'  {k}: {v}')
    print(f'\nWrote {OUT_TRAIN} ({len(train)} rows)')
    print(f'Wrote {OUT_REJECT} ({len(reject)} rows)')
    print(f'Wrote {OUT_REPORT} ({len(report)} rows)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-weak', action='store_true', help='Keep title-only / long-text weak rows')
    args = parser.parse_args()
    main(include_weak=args.include_weak)
