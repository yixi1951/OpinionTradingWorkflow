"""Validate raw posts with OpenClaw free models (authenticity / readability).

Thesis pipeline (strict):
  1) Crawl UGC (e.g. guba API)
  2) OpenClaw free model — verify rows are processable / non-junk (this script)
  3) Jev / DeepSeek — formal sentiment scores for FM/Logit (rescore_raw_cascade.py)

This script does NOT treat OpenClaw as the paper scorer. It writes:
  - openclaw_validated: 1/0
  - openclaw_score: provisional free-model scalar (audit only)
  - is_noise / capture_status when validation fails
and leaves score_source untouched when it is already jev/deepseek; otherwise sets
score_source=pending_llm so the cascade knows the row still needs DS/Jev.

Usage:
  OPENCLAW_URL=http://127.0.0.1:18789 PYTHONPATH=src \\
    python3 scripts/validate_raw_openclaw.py --since 2026-11-01 --max-total-rows 200
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.openclaw_adapter import OpenClawClient  # noqa: E402

THESIS_SCORES = frozenset({"jev", "deepseek"})


def _text(row: pd.Series) -> str:
    parts = [str(row.get("title", "") or ""), str(row.get("content", "") or "")]
    return " ".join(p for p in parts if p.strip()).strip()


def _list_files(raw_dir: Path, since: Optional[str], until: Optional[str]) -> List[Path]:
    out: List[Path] = []
    for path in sorted(raw_dir.glob("raw_posts_*.csv")):
        day = path.stem.replace("raw_posts_", "")
        if since and day < since:
            continue
        if until and day > until:
            continue
        out.append(path)
    return out


def _needs_validate(row: pd.Series, *, force: bool) -> bool:
    if not _text(row):
        return False
    if force:
        return True
    if "openclaw_validated" in row.index:
        val = str(row.get("openclaw_validated", "")).strip().lower()
        if val in {"1", "true", "yes"}:
            return False
    src = str(row.get("score_source", "") or "").lower()
    # Already formally scored — still allow force re-validate, else skip.
    if src in THESIS_SCORES and not force:
        return False
    return True


def validate_file(
    path: Path,
    client: OpenClawClient,
    *,
    batch_size: int,
    max_rows: int,
    force: bool,
    drop_failed: bool,
) -> int:
    df = pd.read_csv(path)
    if df.empty:
        return 0
    for col, default in (
        ("openclaw_validated", 0),
        ("openclaw_score", ""),
        ("is_noise", False),
        ("capture_status", "success"),
        ("score_source", "keyword"),
        ("ai_score", 0.0),
        ("keyword_score", 0.0),
    ):
        if col not in df.columns:
            df[col] = default

    pending = [idx for idx, row in df.iterrows() if _needs_validate(row, force=force)]
    if max_rows > 0:
        pending = pending[:max_rows]
    if not pending:
        return 0

    done = 0
    drop_idx: List[Any] = []
    for start in range(0, len(pending), batch_size):
        chunk = pending[start : start + batch_size]
        texts = [_text(df.loc[i]) for i in chunk]
        scores = None
        for _attempt in range(3):
            scores = client.score_texts(texts)
            if scores and len(scores) == len(chunk):
                break
            time.sleep(1.5)
        if not scores or len(scores) != len(chunk):
            print(f"  {path.name}: batch failed ({len(chunk)} rows)")
            for i in chunk:
                df.at[i, "openclaw_validated"] = 0
                if drop_failed:
                    drop_idx.append(i)
                else:
                    df.at[i, "is_noise"] = True
                    df.at[i, "capture_status"] = "openclaw_reject"
            continue
        for i, score in zip(chunk, scores):
            df.at[i, "openclaw_validated"] = 1
            df.at[i, "openclaw_score"] = float(score)
            # Do not promote OpenClaw to thesis scorer.
            src = str(df.at[i, "score_source"] or "").lower()
            if src not in THESIS_SCORES:
                df.at[i, "score_source"] = "pending_llm"
            done += 1
        print(f"  {path.name}: validated {done}/{len(pending)}")

    if drop_idx:
        df = df.drop(index=drop_idx)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw authenticity validate (not thesis scorer)")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--since", default=None)
    parser.add_argument("--until", default=None)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-total-rows", type=int, default=200)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--drop-failed",
        action="store_true",
        help="Drop rows that fail OpenClaw validation instead of marking is_noise",
    )
    args = parser.parse_args()

    client = OpenClawClient()
    if not client.is_configured():
        print(
            "OPENCLAW_URL / INFERENCE_URL not set. "
            "Start the free OpenClaw gateway, then re-run validation."
        )
        return 2
    probe = client.probe()
    print("openclaw_probe", probe)
    if not probe.get("connected"):
        print("OpenClaw not reachable — abort.")
        return 3

    files = _list_files(Path(args.raw_dir), args.since, args.until)
    remaining = max(0, int(args.max_total_rows))
    total = 0
    for path in files:
        if remaining <= 0:
            break
        n = validate_file(
            path,
            client,
            batch_size=max(1, args.batch_size),
            max_rows=remaining,
            force=args.force,
            drop_failed=args.drop_failed,
        )
        total += n
        remaining -= n
    print(f"Done. OpenClaw-validated rows this run: {total}")
    print("Next: SCORING_PROVIDER=jev,deepseek PYTHONPATH=src python3 scripts/rescore_raw_cascade.py ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
