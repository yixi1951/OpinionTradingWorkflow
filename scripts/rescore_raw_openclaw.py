"""Re-score raw_posts CSV rows via OpenClaw in small batches (incremental save)."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.openclaw_adapter import OpenClawClient  # noqa: E402


def _text_for_row(row: pd.Series) -> str:
    parts = [str(row.get("title", "") or ""), str(row.get("content", "") or "")]
    text = " ".join(p for p in parts if p.strip()).strip()
    return text or str(row.get("title", "") or "")


def _is_noise_row(row: pd.Series) -> bool:
    if str(row.get("is_noise", "")).lower() in {"true", "1"}:
        return True
    return str(row.get("capture_status", "")).lower() == "fallback"


def rescore(
    path: Path,
    batch_size: int = 4,
    max_rows: int = 0,
    retries: int = 1,
) -> None:
    client = OpenClawClient()
    if not client.is_configured():
        raise SystemExit(
            "OPENCLAW_URL not set. Run scripts/run_daily_openclaw.ps1 or start gateway+proxy first."
        )

    df = pd.read_csv(path)
    if "score_source" not in df.columns:
        df["score_source"] = "keyword"

    pending = [
        idx
        for idx, row in df.iterrows()
        if str(row.get("score_source", "keyword")) != "openclaw"
        and _text_for_row(row)
        and not _is_noise_row(row)
    ]
    if max_rows > 0:
        pending = pending[:max_rows]

    total_batches = (len(pending) + batch_size - 1) // batch_size if pending else 0
    print(
        f"Rescoring {len(pending)} / {len(df)} rows "
        f"(batch_size={batch_size}, batches≈{total_batches})"
    )

    for start in range(0, len(pending), batch_size):
        chunk_idx = pending[start : start + batch_size]
        texts = [_text_for_row(df.loc[i]) for i in chunk_idx]
        batch_no = start // batch_size + 1
        scores = None
        for attempt in range(retries + 1):
            t0 = time.time()
            scores = client.score_texts(texts)
            elapsed = round(time.time() - t0, 1)
            if scores and len(scores) == len(chunk_idx):
                print(f"  batch {batch_no}/{total_batches}: ok ({elapsed}s)")
                break
            print(
                f"  batch {batch_no}/{total_batches}: retry {attempt + 1}/{retries + 1} "
                f"({elapsed}s)"
            )
            time.sleep(2)

        if not scores or len(scores) != len(chunk_idx):
            print(f"  batch {batch_no}: failed, keeping keyword scores")
            continue

        for i, score in zip(chunk_idx, scores):
            df.at[i, "ai_score"] = float(score)
            df.at[i, "score_source"] = "openclaw"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        done = min(start + batch_size, len(pending))
        print(f"  saved {done}/{len(pending)} openclaw scores -> {path.name}")

    oc = int((df["score_source"] == "openclaw").sum())
    print(f"Done. OpenClaw-scored rows: {oc}/{len(df)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenClaw batch rescore for raw_posts CSV")
    parser.add_argument(
        "--csv",
        default="",
        help="Path to raw_posts CSV (default: latest in data/raw/)",
    )
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-rows", type=int, default=0, help="0 = all pending rows")
    parser.add_argument("--timeout", type=int, default=0, help="Override OPENCLAW_TIMEOUT seconds")
    parser.add_argument("--retries", type=int, default=1)
    args = parser.parse_args()

    if args.timeout > 0:
        os.environ["OPENCLAW_TIMEOUT"] = str(args.timeout)

    if args.csv:
        target = Path(args.csv)
    else:
        candidates = sorted((ROOT / "data" / "raw").glob("raw_posts_*.csv"))
        if not candidates:
            raise SystemExit("No raw_posts_*.csv found under data/raw/")
        target = candidates[-1]

    rescore(
        target,
        batch_size=max(1, args.batch_size),
        max_rows=max(0, args.max_rows),
        retries=max(0, args.retries),
    )


if __name__ == "__main__":
    main()
