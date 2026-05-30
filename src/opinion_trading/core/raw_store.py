from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List


class RawPostCsvStore:
    def __init__(self, raw_dir: str) -> None:
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def save_partitioned_rows(
        self, trade_date: str, rows: Iterable[Dict]
    ) -> Dict[str, Path]:
        rows_list = [self._normalize_row(row) for row in rows]
        combined_path = self.raw_dir / f"raw_posts_{trade_date}.csv"
        self._write_csv(combined_path, rows_list)

        by_source_dir = self.raw_dir / "by_source"
        by_source_dir.mkdir(parents=True, exist_ok=True)

        source_paths: Dict[str, Path] = {}
        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for row in rows_list:
            grouped[str(row.get("platform", "unknown"))].append(row)

        for platform, platform_rows in grouped.items():
            target = by_source_dir / f"raw_posts_{trade_date}_{platform}.csv"
            self._write_csv(target, platform_rows)
            source_paths[platform] = target

        return {
            "combined": combined_path,
            **{f"source:{platform}": path for platform, path in source_paths.items()},
        }

    def save_failure_logs(
        self, trade_date: str, rows: Iterable[Dict]
    ) -> Dict[str, Path]:
        failure_rows = [
            self._normalize_row(row)
            for row in rows
            if str(row.get("capture_status", "success")).lower() != "success"
        ]

        failure_dir = self.raw_dir / "failures"
        failure_dir.mkdir(parents=True, exist_ok=True)

        combined_path = failure_dir / f"fetch_failures_{trade_date}.jsonl"
        self._write_jsonl(combined_path, failure_rows)

        source_paths: Dict[str, Path] = {}
        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for row in failure_rows:
            grouped[str(row.get("platform", "unknown"))].append(row)

        for platform, platform_rows in grouped.items():
            target = failure_dir / f"fetch_failures_{trade_date}_{platform}.jsonl"
            self._write_jsonl(target, platform_rows)
            source_paths[platform] = target

        return {
            "combined": combined_path,
            **{f"source:{platform}": path for platform, path in source_paths.items()},
        }

    def _write_csv(self, target: Path, rows: List[Dict]) -> None:
        fieldnames = [
            "trade_date",
            "platform",
            "symbol",
            "title",
            "summary",
            "post_time",
            "content",
            "url",
            "source_page",
            "fetch_time",
            "is_noise",
            "capture_status",
            "failure_reason",
            "keyword_score",
            "ai_score",
        ]

        with target.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})

    def _write_jsonl(self, target: Path, rows: List[Dict]) -> None:
        with target.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _normalize_row(self, row: Dict) -> Dict:
        normalized = dict(row)
        normalized.setdefault(
            "summary",
            self._build_summary(
                normalized.get("title", ""), normalized.get("content", "")
            ),
        )
        normalized.setdefault("capture_status", "success")
        normalized.setdefault("failure_reason", "")
        normalized.setdefault("is_noise", False)
        return normalized

    def _build_summary(self, title: object, content: object) -> str:
        title_text = str(title or "").strip()
        content_text = str(content or "").strip()
        if title_text and content_text:
            return f"{title_text} | {content_text[:80]}"[:180]
        return (title_text or content_text)[:180]
