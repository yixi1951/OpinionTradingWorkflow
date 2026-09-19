# ML baseline vs keyword scoring

- Generated: 2026-09-19 06:11
- Samples: **12** (train 8 / test 4)
- TF-IDF centroid accuracy: **50.00%** (macro F1 0.333)
- Keyword lexicon accuracy: **100.00%** (macro F1 0.667)

Research prototype only — tiny labeled sample, not a profitability claim. Keyword/hybrid remains the default scoring path.

| Label | TF-IDF F1 | Keyword F1 |
|---|---:|---:|
| bull | 0.500 | 1.000 |
| bear | 0.500 | 1.000 |
| neutral | 0.000 | 0.000 |
