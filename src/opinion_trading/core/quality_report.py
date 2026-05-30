from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List


class QualityReportBuilder:
    TITLE_THRESHOLD = 0.95
    TIME_THRESHOLD = 0.90
    CONTENT_THRESHOLD = 0.85
    NOISE_THRESHOLD = 0.20

    def __init__(self, report_dir: str) -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def build(self, trade_date: str, raw_rows: Iterable[Dict], raw_csv_path: Path) -> Path:
        rows = list(raw_rows)
        target = self.report_dir / f"quality_{trade_date}.md"

        overall = self._summarize(rows)
        per_platform = self._summarize_by_platform(rows)

        lines: List[str] = []
        lines.append(f"# Raw Data Quality Report - {trade_date}")
        lines.append("")
        lines.append("## Overall")
        lines.extend(self._format_summary(overall))
        lines.append("")
        lines.append("## Per Platform")
        lines.append("| Platform | Rows | Title Coverage | Time Coverage | Content Coverage | Noise Rate | Status |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for platform, summary in per_platform.items():
            lines.append(self._format_platform_row(platform, summary))
        lines.append("")
        lines.append("## Acceptance Rule")
        lines.append(f"- Title coverage >= {self.TITLE_THRESHOLD:.2f}")
        lines.append(f"- Time coverage >= {self.TIME_THRESHOLD:.2f}")
        lines.append(f"- Content coverage >= {self.CONTENT_THRESHOLD:.2f}")
        lines.append(f"- Noise rate <= {self.NOISE_THRESHOLD:.2f}")
        lines.append("")
        lines.append(f"- Raw CSV: {raw_csv_path.as_posix()}")

        target.write_text("\n".join(lines), encoding="utf-8")
        return target

    def _summarize_by_platform(self, rows: List[Dict]) -> Dict[str, Dict[str, float]]:
        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for row in rows:
            grouped[str(row.get("platform", "unknown"))].append(row)
        return {platform: self._summarize(items) for platform, items in sorted(grouped.items())}

    def _summarize(self, rows: List[Dict]) -> Dict[str, float]:
        total = len(rows)
        if total == 0:
            return {
                "rows": 0,
                "title_coverage": 0.0,
                "time_coverage": 0.0,
                "content_coverage": 0.0,
                "noise_rate": 0.0,
                "status": 0.0,
            }

        title_ok = sum(1 for row in rows if self._has_title(row))
        time_ok = sum(1 for row in rows if self._has_time(row))
        content_ok = sum(1 for row in rows if self._has_content(row))
        noise_count = sum(1 for row in rows if self._is_noise(row))

        title_coverage = title_ok / total
        time_coverage = time_ok / total
        content_coverage = content_ok / total
        noise_rate = noise_count / total

        status = self._passes(title_coverage, time_coverage, content_coverage, noise_rate)
        return {
            "rows": float(total),
            "title_coverage": title_coverage,
            "time_coverage": time_coverage,
            "content_coverage": content_coverage,
            "noise_rate": noise_rate,
            "status": 1.0 if status else 0.0,
        }

    def _format_summary(self, summary: Dict[str, float]) -> List[str]:
        status_text = "PASS" if summary["status"] >= 0.5 else "FAIL"
        return [
            f"- Total rows: {int(summary['rows'])}",
            f"- Title coverage: {summary['title_coverage']:.2%}",
            f"- Time coverage: {summary['time_coverage']:.2%}",
            f"- Content coverage: {summary['content_coverage']:.2%}",
            f"- Noise rate: {summary['noise_rate']:.2%}",
            f"- Overall status: {status_text}",
        ]

    def _format_platform_row(self, platform: str, summary: Dict[str, float]) -> str:
        status_text = "PASS" if self._passes(
            summary["title_coverage"],
            summary["time_coverage"],
            summary["content_coverage"],
            summary["noise_rate"],
        ) else "FAIL"
        return (
            f"| {platform} | {int(summary['rows'])} | {summary['title_coverage']:.2%} | "
            f"{summary['time_coverage']:.2%} | {summary['content_coverage']:.2%} | "
            f"{summary['noise_rate']:.2%} | {status_text} |"
        )

    def _passes(self, title_coverage: float, time_coverage: float, content_coverage: float, noise_rate: float) -> bool:
        return (
            title_coverage >= self.TITLE_THRESHOLD
            and time_coverage >= self.TIME_THRESHOLD
            and content_coverage >= self.CONTENT_THRESHOLD
            and noise_rate <= self.NOISE_THRESHOLD
        )

    def _normalize_text(self, value: object) -> str:
        return str(value or "").strip()

    def _has_title(self, row: Dict) -> bool:
        title = self._normalize_text(row.get("title"))
        return len(title) >= 6

    def _has_time(self, row: Dict) -> bool:
        post_time = self._normalize_text(row.get("post_time"))
        if not post_time:
            return False
        return bool(re.search(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", post_time) or re.search(r"\d{1,2}:\d{2}", post_time))

    def _has_content(self, row: Dict) -> bool:
        content = self._normalize_text(row.get("content"))
        return len(content) >= 20

    def _is_noise(self, row: Dict) -> bool:
        title = self._normalize_text(row.get("title"))
        content = self._normalize_text(row.get("content"))
        if len(title) < 6 or len(content) < 20:
            return True

        haystack = f"{title} {content}"
        noise_hits = sum(1 for token in self._noise_tokens() if token in haystack)
        return noise_hits >= 2 or self._looks_like_noise(haystack)

    def _looks_like_noise(self, text: str) -> bool:
        text = text.strip()
        if not text:
            return True
        low = text.lower()
        if len(text) <= 8:
            return True
        if any(token.lower() in low for token in ["登录", "注册", "下载app", "扫一扫", "免责声明", "返回", "举报", "郑重声明"]):
            return True
        return False

    def _noise_tokens(self) -> List[str]:
        return [
            "登录",
            "注册",
            "下载APP",
            "扫一扫",
            "免责声明",
            "返回",
            "举报",
            "郑重声明",
            "风险自担",
            "意见与建议",
            "请勿相信",
            "远离非法证券活动",
            "扫码",
            "APP",
        ]