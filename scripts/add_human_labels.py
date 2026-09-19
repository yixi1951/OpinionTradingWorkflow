#!/usr/bin/env python3
"""Prepare a human-labeling CSV template from raw posts (no labels claimed).

Usage:
  PYTHONPATH=src python scripts/add_human_labels.py \\
      --infile tests/fixtures/raw_posts_smoke_min.csv \\
      --out data/labels/human_label_template.csv

Fill ``label`` with bull | bear | neutral and set ``label_source=human``.
See docs/human_labels_howto.md.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create human label template CSV")
    parser.add_argument("--infile", required=True, help="Raw posts CSV")
    parser.add_argument("--out", required=True, help="Output template path")
    parser.add_argument("--max-rows", type=int, default=200)
    args = parser.parse_args()

    src = Path(args.infile)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with src.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)[: args.max_rows]

    fields = [
        "id",
        "platform",
        "symbol",
        "trade_date",
        "text",
        "label",
        "notes",
        "label_source",
        "annotator",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, row in enumerate(rows, start=1):
            text = str(row.get("content") or row.get("summary") or row.get("title") or "")
            w.writerow(
                {
                    "id": str(i),
                    "platform": row.get("platform", ""),
                    "symbol": row.get("symbol", ""),
                    "trade_date": row.get("trade_date", ""),
                    "text": text[:500],
                    "label": "",
                    "notes": "fill bull|bear|neutral",
                    "label_source": "human",
                    "annotator": "",
                }
            )
    print(f"Wrote template with {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
