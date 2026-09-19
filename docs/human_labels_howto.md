# Adding human labels later (optional)

The repository ships **synthetic** labeled rows in `tests/fixtures/annotation_sample_labeled.csv` (72 balanced rows) so `compare_ml_baseline.py` / `train_eval.py` stay offline in CI. **No production human annotation program is included.**

## Steps

1. Export or sample raw posts:
   ```bash
   PYTHONPATH=src python scripts/sample_annotation.py \
     --infile data/raw/raw_posts_2026-06-17.csv --n 50 \
     --out data/labels/annotation_sample.csv
   ```
2. Create a blank template (or edit the sample):
   ```bash
   PYTHONPATH=src python scripts/add_human_labels.py \
     --infile tests/fixtures/raw_posts_smoke_min.csv \
     --out data/labels/human_label_template.csv
   ```
3. Annotators fill `label` ∈ {`bull`, `bear`, `neutral`}, set `label_source=human`, and `annotator`.
4. Compare baselines (research only):
   ```bash
   PYTHONPATH=src python scripts/compare_ml_baseline.py \
     --labels data/labels/human_label_template.csv
   ```

Guidelines: [annotation_instructions_zh.md](annotation_instructions_zh.md).

**Out of scope here:** paid crowd labeling, inter-annotator adjudication at scale, or replacing walk-forward synthetic history with months of real crawl data.
