"""Merge annotation base CSV with human review CSV (same as label_review_app export)."""
from pathlib import Path

import pandas as pd


def export_review_merged(
    base_path: Path,
    review_path: Path,
    out_path: Path,
    review_cols: tuple[str, ...] = ('id', 'label', 'notes', 'annotator'),
) -> int:
    if not base_path.exists() or not review_path.exists():
        return 0
    base = pd.read_csv(base_path)
    rev = pd.read_csv(review_path)
    cols = [c for c in review_cols if c in rev.columns]
    if 'id' not in cols or 'label' not in cols:
        return 0
    merged = base.merge(rev[cols], on='id', how='left', suffixes=('', '_review'))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False, encoding='utf-8-sig')
    labeled = merged['label_review'].notna().sum() if 'label_review' in merged.columns else rev['label'].notna().sum()
    return int(labeled)
