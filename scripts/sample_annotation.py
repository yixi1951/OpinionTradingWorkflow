"""从 memory 中抽取样本用于人工标注

用法示例：
  python scripts/sample_annotation.py --n 100 --seed 42

输出：data/labels/annotation_sample.csv
"""
import argparse
from pathlib import Path
import pandas as pd


def main(n: int, seed: int, infile: str, out: str):
    p = Path(infile)
    if not p.exists():
        print(f"Input file not found: {infile}")
        return
    df = pd.read_json(p, lines=True)
    if df.empty:
        print("No rows in input file")
        return
    # choose a text column
    text_col = None
    for c in ["text", "content", "summary", "title"]:
        if c in df.columns:
            text_col = c
            break
    if text_col is None:
        # fallback: stringify the row
        df["text"] = df.astype(str).agg(" ".join, axis=1)
        text_col = "text"

    sample = df.sample(n=min(n, len(df)), random_state=seed).reset_index(drop=True)
    sample["id"] = sample.index + 1

    out_cols = ["id", "platform", "symbol", "trade_date", text_col]
    # ensure columns exist
    for c in ["platform", "symbol", "trade_date", text_col]:
        if c not in sample.columns:
            sample[c] = ""

    out_df = sample[["id", "platform", "symbol", "trade_date", text_col]].copy()
    out_df = out_df.rename(columns={text_col: "text"})
    out_df["label"] = ""
    out_df["notes"] = ""

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(out_df)} rows to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--infile", type=str, default="data/memory/sentiment_history.jsonl")
    parser.add_argument("--out", type=str, default="data/labels/annotation_sample.csv")
    args = parser.parse_args()
    main(args.n, args.seed, args.infile, args.out)
