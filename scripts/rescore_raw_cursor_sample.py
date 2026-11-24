"""Apply a small offline Cursor-agent score sample into raw CSVs.

This path burns Cursor chat quota (human/agent judgment), not DeepSeek/Jev API.
Input CSV columns: _file, _idx, ai_score (and optional title/symbol for audit).

Usage:
  PYTHONPATH=src python3 scripts/rescore_raw_cursor_sample.py \\
    --scores /tmp/cursor_score_sample_scored.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def apply_scores(scores_csv: Path, *, source: str = "cursor_llm") -> int:
    sample = pd.read_csv(scores_csv)
    required = {"_file", "_idx", "ai_score"}
    missing = required - set(sample.columns)
    if missing:
        raise SystemExit(f"scores CSV missing columns: {sorted(missing)}")

    updated = 0
    for fpath, group in sample.groupby("_file"):
        path = Path(str(fpath))
        if not path.is_file():
            path = ROOT / path
        if not path.is_file():
            print(f"skip missing file: {fpath}")
            continue
        df = pd.read_csv(path)
        if "score_source" not in df.columns:
            df["score_source"] = "keyword"
        if "ai_score" not in df.columns:
            df["ai_score"] = df.get("keyword_score", 0.0)
        for _, row in group.iterrows():
            idx = int(row["_idx"])
            if idx not in df.index and idx >= len(df):
                print(f"  bad idx {idx} in {path.name}")
                continue
            df.at[idx, "ai_score"] = float(row["ai_score"])
            df.at[idx, "score_source"] = source
            updated += 1
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"updated {path.name}: +{len(group)}")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Cursor-agent score sample")
    parser.add_argument("--scores", required=True, help="CSV with _file,_idx,ai_score")
    parser.add_argument("--source", default="cursor_llm")
    args = parser.parse_args()
    n = apply_scores(Path(args.scores), source=args.source)
    print(f"Done. rows={n}")


if __name__ == "__main__":
    main()
