"""从 memory / raw CSV 抽取样本用于人工标注

用法示例：
  python scripts/sample_annotation.py --n 100 --seed 42
  python scripts/sample_annotation.py --infile tests/fixtures/raw_posts_smoke_min.csv
  python scripts/sample_annotation.py --infile data/raw/raw_posts_*.csv

输出：data/labels/annotation_sample.csv
列：id,platform,symbol,trade_date,text,label,notes,label_source,annotator
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".csv", ".tsv"}:
        sep = "," if path.suffix.lower() == ".csv" else "\t"
        return pd.read_csv(path, sep=sep)
    return pd.read_json(path, lines=True)


def load_source(infile: str) -> pd.DataFrame:
    p = Path(infile)
    if "*" in infile or "?" in infile:
        frames = []
        parent = p.parent if str(p.parent) not in {"", "."} else Path(".")
        for match in sorted(parent.glob(p.name)):
            if match.is_file():
                frames.append(_read_table(match))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)
    if not p.exists():
        return pd.DataFrame()
    return _read_table(p)


def sample_annotation_frame(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
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
        )
    work = df.copy()
    text_col = None
    for c in ["text", "content", "summary", "title"]:
        if c in work.columns:
            text_col = c
            break
    if text_col is None:
        work["text"] = work.astype(str).agg(" ".join, axis=1)
        text_col = "text"

    sample = work.sample(n=min(n, len(work)), random_state=seed).reset_index(drop=True)
    sample["id"] = sample.index + 1
    for c in ["platform", "symbol", "trade_date"]:
        if c not in sample.columns:
            sample[c] = ""
    out_df = sample[["id", "platform", "symbol", "trade_date", text_col]].copy()
    out_df = out_df.rename(columns={text_col: "text"})
    out_df["label"] = ""
    out_df["notes"] = ""
    out_df["label_source"] = ""
    out_df["annotator"] = ""
    return out_df


def main(n: int, seed: int, infile: str, out: str) -> None:
    df = load_source(infile)
    if df.empty:
        print(f"Input file not found or empty: {infile}")
        return
    out_df = sample_annotation_frame(df, n, seed)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(out_df)} rows to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--infile",
        type=str,
        default="data/memory/sentiment_history.jsonl",
    )
    parser.add_argument("--out", type=str, default="data/labels/annotation_sample.csv")
    args = parser.parse_args()
    main(args.n, args.seed, args.infile, args.out)
