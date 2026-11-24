"""Mark low-precision raw posts as is_noise before LLM scoring.

Does not delete rows. Sets:
  - is_noise = True
  - noise_reason = semicolon-joined quality_issues
  - capture_status = quality_reject (when not already a harder failure)

Usage:
  PYTHONPATH=scripts python3 scripts/filter_raw_opinion_quality.py \\
    --since 2026-09-01 --dry-run
  PYTHONPATH=scripts python3 scripts/filter_raw_opinion_quality.py \\
    --since 2026-09-01 --apply
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from text_quality import (  # noqa: E402
    is_precise_opinion,
    pick_comment_text,
    quality_issues,
)

HARD_FAIL = frozenset({"failed", "error", "fallback", "openclaw_reject", "quality_reject"})


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


def _body(row: pd.Series) -> str:
    return pick_comment_text(
        str(row.get("text", "") or ""),
        title=str(row.get("title", "") or ""),
        content=str(row.get("content", "") or ""),
        summary=str(row.get("summary", "") or ""),
    )


def filter_file(path: Path, *, apply: bool) -> dict:
    df = pd.read_csv(path)
    if df.empty:
        return {"file": path.name, "rows": 0, "marked": 0, "kept": 0}
    for col, default in (
        ("is_noise", False),
        ("noise_reason", ""),
        ("capture_status", "success"),
    ):
        if col not in df.columns:
            df[col] = default

    marked = 0
    reasons: Counter[str] = Counter()
    for idx, row in df.iterrows():
        already = str(row.get("is_noise", "")).lower() in {"true", "1", "yes"}
        body = _body(row)
        title = str(row.get("title", "") or "")
        plat = str(row.get("platform", "") or "")
        url = str(row.get("url", "") or "")
        issues = quality_issues(body or title, title=title, platform=plat, url=url)
        precise = is_precise_opinion(
            body or title, platform=plat, url=url, title=title, min_cjk=8
        )
        if precise and not issues:
            continue
        if not issues and not precise:
            issues = ["imprecise"]
        marked += 1
        for issue in issues:
            reasons[issue] += 1
        if apply and not already:
            df.at[idx, "is_noise"] = True
            df.at[idx, "noise_reason"] = ";".join(issues)
            status = str(df.at[idx, "capture_status"] or "").lower()
            if status not in HARD_FAIL:
                df.at[idx, "capture_status"] = "quality_reject"

    if apply and marked:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    kept = int((~df["is_noise"].astype(str).str.lower().isin({"true", "1", "yes"})).sum()) if apply else (
        len(df) - marked
    )
    return {
        "file": path.name,
        "rows": len(df),
        "marked": marked,
        "kept": kept,
        "top_reasons": dict(reasons.most_common(8)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mark invalid / low-value raw opinions as noise")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--since", default=None)
    parser.add_argument("--until", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Report only (default)")
    parser.add_argument("--apply", action="store_true", help="Write is_noise / noise_reason back to CSV")
    args = parser.parse_args()
    apply = bool(args.apply) and not args.dry_run

    files = _list_files(Path(args.raw_dir), args.since, args.until)
    if not files:
        print("No raw files matched.")
        return 1

    total_rows = total_marked = total_kept = 0
    reason_all: Counter[str] = Counter()
    for path in files:
        stats = filter_file(path, apply=apply)
        total_rows += stats["rows"]
        total_marked += stats["marked"]
        total_kept += stats["kept"]
        for k, v in (stats.get("top_reasons") or {}).items():
            reason_all[k] += v
        mode = "APPLY" if apply else "DRY"
        print(
            f"[{mode}] {stats['file']}: rows={stats['rows']} "
            f"reject={stats['marked']} keep≈{stats['kept']} "
            f"reasons={stats.get('top_reasons')}"
        )

    rate = (100.0 * total_marked / total_rows) if total_rows else 0.0
    print(
        f"\nSummary: files={len(files)} rows={total_rows} "
        f"reject={total_marked} ({rate:.1f}%) keep≈{total_kept}"
    )
    print(f"Top reasons: {dict(reason_all.most_common(12))}")
    if not apply:
        print("Dry-run only. Re-run with --apply to mark is_noise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
