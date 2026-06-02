from pathlib import Path
import pandas as pd

root = Path('data/labels')
src = root / 'annotation_sample_labeled.csv'
out = root / 'annotation_sample_for_training.csv'

df = pd.read_csv(src)
if 'consensus_label' not in df.columns:
    raise SystemExit('consensus_label not found in source')
# prefer consensus_label, fall back to human_label_cat
df['train_label'] = df['consensus_label'].fillna(df.get('human_label_cat'))
# drop conflicts
keep = df['train_label'] != 'conflict'
df2 = df[keep].copy()
# ensure text column exists
if 'text' not in df2.columns:
    raise SystemExit('text column missing')
# write minimal CSV for training
df2[['text', 'train_label']].rename(columns={'train_label': 'label'}).to_csv(out, index=False)
print(f'Wrote {out} ({len(df2)} rows)')
