#!/usr/bin/env python3
"""Export unlabeled rows for human annotation."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.human_labels_workflow import (
    export_unlabeled_from_raw,
    export_unlabeled_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export unlabeled label template")
    parser.add_argument("--infile", help="Single raw_posts CSV")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--out", default="data/labels/unlabeled_export.csv")
    parser.add_argument("--max-rows", type=int, default=200)
    args = parser.parse_args()
    if args.infile:
        info = export_unlabeled_from_raw(args.infile, args.out, max_rows=args.max_rows)
    else:
        info = export_unlabeled_jsonl(args.raw_dir, args.out, max_rows=args.max_rows)
    print(info)


if __name__ == "__main__":
    main()
