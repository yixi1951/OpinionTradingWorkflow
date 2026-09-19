"""Compare offline TF-IDF centroid baseline vs keyword scoring.

Usage:
  PYTHONPATH=src python scripts/compare_ml_baseline.py \\
      --labels tests/fixtures/annotation_sample_labeled.csv \\
      --out data/reports/ml_baseline_comparison.md
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

# Keep the comparison offline (no LLM gateway).
os.environ.setdefault("USE_LLM_GATEWAY", "0")
os.environ.setdefault("HYBRID_USE_LLM", "0")
os.environ.setdefault("SCORING_MODE", "keyword")
os.environ.setdefault("OPENCLAW_SKIP_ROW_SCORE", "1")


def main() -> None:
    parser = argparse.ArgumentParser(description="TF-IDF vs keyword baseline report")
    parser.add_argument(
        "--labels",
        type=str,
        default="tests/fixtures/annotation_sample_labeled.csv",
        help="Labeled CSV with columns text,label (bull/bear/neutral)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="data/reports/ml_baseline_comparison.md",
    )
    parser.add_argument("--test-size", type=float, default=0.34)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    from opinion_trading.core.ml_baseline import (
        compare_tfidf_vs_keyword,
        load_labeled_csv,
        write_comparison_report,
    )

    df = load_labeled_csv(args.labels)
    report, _clf = compare_tfidf_vs_keyword(
        df, test_size=args.test_size, seed=args.seed
    )
    outputs = write_comparison_report(report, args.out)
    print("=== ML baseline comparison (research prototype) ===")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    print(f"Wrote {outputs['md']}")
    print(f"Wrote {outputs['json']}")


if __name__ == "__main__":
    main()
