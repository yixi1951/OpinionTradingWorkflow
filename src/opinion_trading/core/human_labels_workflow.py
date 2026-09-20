"""Export / import helpers for human annotation CSV workflow (offline)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from opinion_trading.core.ml_baseline import LABELS, _SCHEMA_COLS, load_labeled_csv

_EXPORT_FIELDS = list(_SCHEMA_COLS)


def export_unlabeled_from_raw(
    raw_path: str | Path,
    out_path: str | Path,
    *,
    max_rows: int = 200,
    only_empty_label: bool = True,
) -> Dict[str, Any]:
    """Write rows without labels (or all rows) for human annotation."""
    src = Path(raw_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows_out: List[Dict[str, str]] = []
    with src.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            if len(rows_out) >= max_rows:
                break
            label = str(row.get("label", "")).strip().lower()
            if only_empty_label and label in LABELS:
                continue
            text = str(row.get("text") or row.get("content") or row.get("title") or "")
            rows_out.append(
                {
                    "id": str(row.get("id") or i),
                    "platform": str(row.get("platform", "")),
                    "symbol": str(row.get("symbol", "")),
                    "trade_date": str(row.get("trade_date", "")),
                    "text": text[:500],
                    "label": "",
                    "notes": "",
                    "label_source": "",
                    "annotator": "",
                }
            )
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_EXPORT_FIELDS)
        w.writeheader()
        for row in rows_out:
            w.writerow(row)
    return {"path": str(out), "rows": len(rows_out), "source": str(src)}


def export_unlabeled_jsonl(
    raw_dir: str | Path,
    out_path: str | Path,
    *,
    max_rows: int = 200,
) -> Dict[str, Any]:
    """Sample unlabeled rows from latest raw_posts_*.csv in raw_dir."""
    root = Path(raw_dir)
    candidates = sorted(root.glob("raw_posts_*.csv"))
    if not candidates:
        return {"path": str(out_path), "rows": 0, "error": "no raw_posts_*.csv"}
    latest = candidates[-1]
    return export_unlabeled_from_raw(latest, out_path, max_rows=max_rows)


def validate_human_import_df(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    errors: List[str] = []
    for col in ("text", "label"):
        if col not in df.columns:
            errors.append(f"missing column: {col}")
    if errors:
        return df, errors
    work = df.copy()
    work["label"] = work["label"].astype(str).str.strip().str.lower()
    work["label_source"] = work.get("label_source", pd.Series([""] * len(work)))
    work["label_source"] = work["label_source"].astype(str).str.strip().str.lower()
    bad_label = ~work["label"].isin(LABELS)
    if bad_label.any():
        errors.append(f"invalid label on {int(bad_label.sum())} rows")
    bad_src = work["label_source"] != "human"
    if bad_src.any():
        errors.append(
            f"label_source must be 'human' on all rows ({int(bad_src.sum())} violations)"
        )
    work = work[work["label"].isin(LABELS) & (work["label_source"] == "human")]
    return work.reset_index(drop=True), errors


def import_human_labels_csv(
    in_path: str | Path,
    out_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    df = pd.read_csv(in_path)
    cleaned, errors = validate_human_import_df(df)
    result: Dict[str, Any] = {
        "source": str(in_path),
        "rows_valid": len(cleaned),
        "errors": errors,
        "ok": not errors and len(cleaned) > 0,
    }
    if out_path and result["ok"]:
        dest = Path(out_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        cleaned.to_csv(dest, index=False)
        result["path"] = str(dest)
    return result


def score_human_labels_report(
    labels_path: str | Path,
    *,
    test_size: float = 0.34,
    seed: int = 42,
) -> Dict[str, Any]:
    from opinion_trading.core.ml_baseline import compare_tfidf_vs_keyword

    df = load_labeled_csv(labels_path)
    report, _ = compare_tfidf_vs_keyword(df, test_size=test_size, seed=seed)
    return report.to_dict()


def write_baseline_report_md(report: Dict[str, Any], out_path: str | Path) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Human labels vs baselines",
        "",
        f"- n_train: {report.get('n_train')}",
        f"- n_test: {report.get('n_test')}",
        f"- keyword_accuracy: {report.get('keyword_accuracy')}",
        f"- tfidf_accuracy: {report.get('tfidf_accuracy')}",
        "",
        "```json",
        json.dumps(report, ensure_ascii=False, indent=2),
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
