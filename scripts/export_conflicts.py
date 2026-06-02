from pathlib import Path
import pandas as pd

root = Path('data/labels')
src = root / 'annotation_sample_labeled.csv'
out = root / 'conflicts_review.csv'

df = pd.read_csv(src)
if 'consensus_label' not in df.columns:
    print('consensus_label not found')
    raise SystemExit(1)
conf = df[df['consensus_label'] == 'conflict']
conf.to_csv(out, index=False)
print(f'Wrote {out} ({len(conf)} rows)')
