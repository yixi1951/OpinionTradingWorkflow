"""Re-score data/raw posts via thesis cascade: Jev → DeepSeek (optional Qwen).

Pipeline context:
  OpenClaw free model = crawl authenticity gate (validate_raw_openclaw.py)
  This script = formal paper scores (Jev / DeepSeek only by default)

Keeps ``keyword_score`` intact; writes scalars into ``ai_score`` and
``score_source`` (jev / deepseek). Thesis ``sent_llm`` only counts these sources.

Usage:
  SCORING_MODE=ai TYPESAFE_API_KEY=... DEEPSEEK_API_KEY=... \\
    PYTHONPATH=src python3 scripts/rescore_raw_cascade.py --since 2026-09-15

  # Thesis default: Jev → DeepSeek (no keyword paper path)
  SCORING_PROVIDER=jev,deepseek PYTHONPATH=src python3 scripts/rescore_raw_cascade.py \\
    --max-total-rows 80 --per-symbol 1
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.ai_sentiment import AISentimentAnalyzer  # noqa: E402
from opinion_trading.core.jev_client import jev_configured  # noqa: E402
from opinion_trading.core.llm_failover import any_live_key  # noqa: E402


# Formal thesis sources. OpenClaw / pending_llm / keyword still need this script.
THESIS_SOURCES = frozenset({"jev", "deepseek"})
LIVE_SOURCES = frozenset({"jev", "deepseek", "qwen", "cursor_llm"})


def _text_for_row(row: pd.Series) -> str:
    parts = [str(row.get("title", "") or ""), str(row.get("content", "") or "")]
    text = " ".join(p for p in parts if p.strip()).strip()
    return text or str(row.get("title", "") or "")


def _is_noise_row(row: pd.Series) -> bool:
    if str(row.get("is_noise", "")).lower() in {"true", "1", "yes"}:
        return True
    return str(row.get("capture_status", "")).lower() in {
        "fallback",
        "error",
        "blocked",
        "empty",
    }


def _needs_rescore(row: pd.Series, *, force: bool) -> bool:
    if _is_noise_row(row):
        return False
    if not _text_for_row(row):
        return False
    if force:
        return True
    src = str(row.get("score_source", "keyword") or "keyword").lower()
    # Prefer re-scoring anything that is not yet Jev/DeepSeek for the thesis path.
    return src not in THESIS_SOURCES


def _list_raw_csvs(
    raw_dir: Path,
    *,
    since: Optional[str],
    until: Optional[str],
) -> List[Path]:
    files = sorted(raw_dir.glob("raw_posts_*.csv"))
    out: List[Path] = []
    for path in files:
        day = path.stem.replace("raw_posts_", "")
        if since and day < since:
            continue
        if until and day > until:
            continue
        out.append(path)
    return out


def _pending_indices(df: pd.DataFrame, *, force: bool) -> List[Any]:
    return [idx for idx, row in df.iterrows() if _needs_rescore(row, force=force)]


def _stratified_take(
    df: pd.DataFrame,
    pending: Sequence[Any],
    *,
    limit: int,
    per_symbol: int,
) -> List[Any]:
    """Prefer diverse symbols; caps total and optional per-symbol quota."""
    if limit <= 0 and per_symbol <= 0:
        return list(pending)
    by_sym: Dict[str, List[Any]] = {}
    for idx in pending:
        sym = str(df.at[idx, "symbol"] if "symbol" in df.columns else "").upper() or "_"
        by_sym.setdefault(sym, []).append(idx)
    picked: List[Any] = []
    # Round-robin across symbols for panel coverage with few API calls.
    queues = {s: list(idxs) for s, idxs in by_sym.items()}
    per_counts = {s: 0 for s in queues}
    while queues:
        progress = False
        for sym in list(queues.keys()):
            if limit > 0 and len(picked) >= limit:
                return picked
            if per_symbol > 0 and per_counts[sym] >= per_symbol:
                queues.pop(sym, None)
                continue
            bucket = queues.get(sym) or []
            if not bucket:
                queues.pop(sym, None)
                continue
            picked.append(bucket.pop(0))
            per_counts[sym] += 1
            progress = True
            if not bucket:
                queues.pop(sym, None)
        if not progress:
            break
    return picked


def rescore_file(
    path: Path,
    analyzer: AISentimentAnalyzer,
    *,
    batch_size: int,
    max_rows: int,
    per_symbol: int,
    force: bool,
    retries: int,
    sleep_s: float,
    budget_left: Optional[int] = None,
) -> Dict[str, Any]:
    df = pd.read_csv(path)
    if "keyword_score" not in df.columns:
        df["keyword_score"] = 0.0
    if "ai_score" not in df.columns:
        df["ai_score"] = df["keyword_score"]
    if "score_source" not in df.columns:
        df["score_source"] = "keyword"

    pending = _pending_indices(df, force=force)
    file_cap = max_rows if max_rows > 0 else 0
    if budget_left is not None:
        if budget_left <= 0:
            return {
                "file": path.name,
                "total": len(df),
                "pending": 0,
                "scored": 0,
                "by_source": {},
                "failed_batches": 0,
                "skipped_budget": True,
            }
        file_cap = budget_left if file_cap <= 0 else min(file_cap, budget_left)
    pending = _stratified_take(
        df, pending, limit=file_cap, per_symbol=max(0, per_symbol)
    )

    stats: Dict[str, Any] = {
        "file": path.name,
        "total": len(df),
        "pending": len(pending),
        "scored": 0,
        "by_source": {},
        "failed_batches": 0,
    }
    if not pending:
        print(f"{path.name}: nothing pending ({len(df)} rows)")
        return stats

    total_batches = (len(pending) + batch_size - 1) // batch_size
    print(
        f"{path.name}: rescoring {len(pending)}/{len(df)} "
        f"(batch={batch_size}, batches≈{total_batches})"
    )

    for start in range(0, len(pending), batch_size):
        chunk_idx = pending[start : start + batch_size]
        texts = [_text_for_row(df.loc[i]) for i in chunk_idx]
        batch_no = start // batch_size + 1
        results = None
        for attempt in range(retries + 1):
            t0 = time.time()
            try:
                results = analyzer.analyze_texts(texts)
            except Exception as exc:
                print(
                    f"  batch {batch_no}/{total_batches}: error {exc!r} "
                    f"(attempt {attempt + 1}/{retries + 1})"
                )
                results = None
            elapsed = round(time.time() - t0, 1)
            if results is not None and len(results) == len(chunk_idx):
                sources = sorted({r.source for r in results})
                print(
                    f"  batch {batch_no}/{total_batches}: ok {elapsed}s "
                    f"sources={sources}"
                )
                break
            time.sleep(max(0.5, sleep_s) * (attempt + 1))

        if results is None or len(results) != len(chunk_idx):
            stats["failed_batches"] += 1
            print(f"  batch {batch_no}: failed — keep prior scores")
            continue

        for offset, (i, result) in enumerate(zip(chunk_idx, results)):
            # Preserve dictionary score; LLM/Jev goes to ai_score only.
            prev_kw = df.at[i, "keyword_score"]
            if prev_kw is None or prev_kw == "" or (isinstance(prev_kw, float) and pd.isna(prev_kw)):
                df.at[i, "keyword_score"] = float(
                    analyzer._keyword_result(texts[offset]).score
                )
            df.at[i, "ai_score"] = float(result.score)
            df.at[i, "score_source"] = str(result.source)
            stats["scored"] += 1
            src = str(result.source)
            stats["by_source"][src] = int(stats["by_source"].get(src, 0)) + 1

        df.to_csv(path, index=False, encoding="utf-8-sig")
        done = min(start + batch_size, len(pending))
        print(f"  saved {done}/{len(pending)} -> {path.name}")
        if sleep_s > 0:
            time.sleep(sleep_s)

    return stats


def ensure_live_ready(*, require: bool) -> None:
    os.environ.setdefault("SCORING_MODE", "ai")
    # Thesis landing path: Jev → DeepSeek only (OpenClaw is validate-only).
    os.environ.setdefault("SCORING_PROVIDER", "jev,deepseek")
    has_jev = jev_configured()
    has_llm = any_live_key()
    print(f"SCORING_MODE={os.environ.get('SCORING_MODE')}")
    print(f"SCORING_PROVIDER={os.environ.get('SCORING_PROVIDER')}")
    print(f"jev_configured={has_jev} any_live_key={has_llm}")
    if require and not (has_jev or has_llm):
        raise SystemExit(
            "No live scorer configured. Set TYPESAFE_API_KEY/JEV_API_KEY "
            "(preferred for thesis) and/or DEEPSEEK_API_KEY."
        )
    if require and not has_jev:
        print(
            "WARNING: Jev not configured — cascade will use DeepSeek. "
            "Thesis prefers score_source=jev; add JEV_API_KEY / TYPESAFE_API_KEY."
        )

def main() -> None:
    parser = argparse.ArgumentParser(description="Jev→DeepSeek cascade rescore for raw CSVs")
    parser.add_argument("--raw-dir", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--since", default="", help="Inclusive YYYY-MM-DD")
    parser.add_argument("--until", default="", help="Inclusive YYYY-MM-DD")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--max-rows-per-file", type=int, default=0, help="0 = all pending")
    parser.add_argument(
        "--max-total-rows",
        type=int,
        default=0,
        help="Hard cap across all files (0 = unlimited). Use for frugal runs.",
    )
    parser.add_argument(
        "--per-symbol",
        type=int,
        default=0,
        help="Max rows per symbol inside each file (0 = no per-symbol cap)",
    )
    parser.add_argument("--max-files", type=int, default=0, help="0 = all matching files")
    parser.add_argument("--force", action="store_true", help="Rescore even if already live")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--sleep", type=float, default=0.1, help="Pause between batches")
    parser.add_argument(
        "--allow-keyword-fallback",
        action="store_true",
        help="Do not exit when no API keys (will write keyword sources)",
    )
    args = parser.parse_args()

    ensure_live_ready(require=not args.allow_keyword_fallback)
    analyzer = AISentimentAnalyzer()

    files = _list_raw_csvs(
        Path(args.raw_dir),
        since=args.since.strip() or None,
        until=args.until.strip() or None,
    )
    if args.max_files > 0:
        files = files[: args.max_files]
    if not files:
        raise SystemExit("No raw_posts_*.csv matched filters")

    budget = max(0, args.max_total_rows)
    print(
        f"Files to process: {len(files)} ({files[0].name} .. {files[-1].name}) "
        f"| max_total_rows={budget or '∞'} per_symbol={args.per_symbol or '∞'}"
    )
    summaries: List[Dict[str, Any]] = []
    t0 = time.time()
    # Newest days first — more relevant for short thesis windows.
    for path in reversed(files):
        if budget > 0 and budget <= 0:
            print("Hit --max-total-rows budget; stopping.")
            break
        left = None if budget <= 0 else budget
        stats = rescore_file(
            path,
            analyzer,
            batch_size=max(1, args.batch_size),
            max_rows=max(0, args.max_rows_per_file),
            per_symbol=max(0, args.per_symbol),
            force=bool(args.force),
            retries=max(0, args.retries),
            sleep_s=max(0.0, args.sleep),
            budget_left=left,
        )
        summaries.append(stats)
        if budget > 0:
            budget -= int(stats.get("scored") or 0)
            if budget <= 0:
                print("Hit --max-total-rows budget; stopping.")
                break

    elapsed = time.time() - t0
    scored = sum(int(s["scored"]) for s in summaries)
    failed = sum(int(s["failed_batches"]) for s in summaries)
    by_src: Dict[str, int] = {}
    for s in summaries:
        for k, v in (s.get("by_source") or {}).items():
            by_src[k] = by_src.get(k, 0) + int(v)
    print(
        f"Done in {elapsed:.1f}s | scored={scored} failed_batches={failed} "
        f"by_source={by_src}"
    )


if __name__ == "__main__":
    main()
