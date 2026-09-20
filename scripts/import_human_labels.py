#!/usr/bin/env python3
"""Validate and import human-labeled CSV (label_source=human)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.human_labels_workflow import (
    import_human_labels_csv,
    score_human_labels_report,
    write_baseline_report_md,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import human labels CSV")
    parser.add_argument("--infile", required=True)
    parser.add_argument("--out", default="data/labels/human_imported.csv")
    parser.add_argument(
        "--report",
        default="data/reports/human_labels_baseline.md",
    )
    args = parser.parse_args()
    info = import_human_labels_csv(args.infile, out_path=args.out)
    print(info)
    if not info.get("ok"):
        raise SystemExit(1)
    report = score_human_labels_report(args.out)
    write_baseline_report_md(report, args.report)
    print(f"Wrote baseline report -> {args.report}")


if __name__ == "__main__":
    main()
