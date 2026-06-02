import pandas as pd
from pathlib import Path
import argparse

RAW_DIR = Path('data/raw')
OUT = Path('data/labels/annotation_bulk.csv')


def main(n=500, seed=42):
    files = list(RAW_DIR.glob('*.csv'))
    if not files:
        print('No raw files found in', RAW_DIR)
        return
    parts = []
    for f in files:
        try:
            df = pd.read_csv(f)
            parts.append(df)
        except Exception as e:
            print('skip', f, e)
    if not parts:
        print('No readable raw files')
        return
    all_df = pd.concat(parts, ignore_index=True)
    if all_df.empty:
        print('No rows in raw files')
        return
    n = min(n, len(all_df))
    sample = all_df.sample(n=n, random_state=seed)
    # prefer content/summary/title; ensure a 'text' column
    if 'text' not in sample.columns:
        for c in ('content','summary','title'):
            if c in sample.columns:
                sample['text'] = sample[c].astype(str)
                break
    if 'text' not in sample.columns:
        sample['text'] = sample.astype(str).agg(' '.join, axis=1)
    # keep some meta columns if exist
    cols = [c for c in ['trade_date','platform','symbol','text','title','summary','content','url'] if c in sample.columns]
    out_df = sample[cols] if cols else sample[['text']]
    out_df.to_csv(OUT, index=False, encoding='utf-8-sig')
    print(f'Wrote {OUT} ({len(out_df)} rows)')
    # also write a base copy for auto-labeling pipeline
    base_copy = Path('data/labels/annotation_bulk_openclaw.csv')
    out_df.to_csv(base_copy, index=False, encoding='utf-8-sig')
    print(f'Also wrote {base_copy} ({len(out_df)} rows)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=500)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    main(n=args.n, seed=args.seed)
