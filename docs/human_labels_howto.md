# Human annotation export / import (optional)

The repository ships **synthetic** labeled rows in `tests/fixtures/annotation_sample_labeled.csv` (72 balanced rows) so `compare_ml_baseline.py` / `train_eval.py` stay offline in CI. **No production human annotation program is included.**

## End-to-end checklist

1. **Export unlabeled samples** from raw crawl or fixtures:
   ```bash
   PYTHONPATH=src python scripts/export_unlabeled_labels.py \
     --infile tests/fixtures/raw_posts_smoke_min.csv \
     --out data/labels/unlabeled_export.csv

   # Or latest file under data/raw/
   PYTHONPATH=src python scripts/export_unlabeled_labels.py --raw-dir data/raw
   ```
   CLI equivalent:
   ```bash
   PYTHONPATH=src python -m opinion_trading.main --mode human-labels-export \
     --infile tests/fixtures/raw_posts_smoke_min.csv \
     --labels-out data/labels/unlabeled_export.csv
   ```

2. **Annotate** — fill `label` ∈ {`bull`, `bear`, `neutral`}, set `label_source=human`, and `annotator`.

3. **Import + validate schema**:
   ```bash
   PYTHONPATH=src python scripts/import_human_labels.py \
     --infile data/labels/my_labeled.csv \
     --out data/labels/human_imported.csv
   ```
   Or:
   ```bash
   PYTHONPATH=src python -m opinion_trading.main --mode human-labels-import \
     --labels-in data/labels/my_labeled.csv
   ```

4. **Score vs keyword / TF-IDF baseline** (research only):
   ```bash
   PYTHONPATH=src python scripts/compare_ml_baseline.py \
     --labels data/labels/human_imported.csv
   ```

5. **Template helper** (blank rows):
   ```bash
   PYTHONPATH=src python scripts/add_human_labels.py \
     --infile tests/fixtures/raw_posts_smoke_min.csv \
     --out data/labels/human_label_template.csv
   ```

Guidelines: [annotation_instructions_zh.md](annotation_instructions_zh.md).

**Out of scope here:** paid crowd labeling, inter-annotator adjudication at scale, or replacing walk-forward synthetic history with months of real crawl data (see [crawl_persistence.md](crawl_persistence.md)).
