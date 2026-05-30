from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List


def build_daily_summary(
    trade_date: str, rows: Iterable[Dict], out_dir: str
) -> Dict[str, Path]:
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    rows_list = list(rows)

    # aggregate per platform
    per_platform = defaultdict(list)
    for r in rows_list:
        per_platform[str(r.get("platform", "unknown"))].append(r)

    csv_lines: List[str] = []
    csv_header = [
        "trade_date",
        "platform",
        "total_rows",
        "success_count",
        "failure_count",
        "success_rate",
        "noise_count",
        "noise_rate",
        "title_coverage",
        "time_coverage",
        "content_coverage",
    ]
    csv_lines.append(",".join(csv_header))

    md_lines: List[str] = []
    md_lines.append(f"# Daily Collection Summary - {trade_date}")
    md_lines.append("")
    md_lines.append(
        "| Platform | Total | Success | Fail | Success% | Noise% | Title% | Time% | Content% |"
    )
    md_lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for platform, items in sorted(per_platform.items()):
        total = len(items)
        success = sum(
            1 for it in items if str(it.get("capture_status", "")).lower() == "success"
        )
        failure = total - success
        success_rate = success / total if total else 0.0
        noise = sum(1 for it in items if bool(it.get("is_noise")))
        noise_rate = noise / total if total else 0.0

        title_cov = (
            sum(1 for it in items if str(it.get("title", "")).strip()) / total
            if total
            else 0.0
        )
        time_cov = (
            sum(1 for it in items if str(it.get("post_time", "")).strip()) / total
            if total
            else 0.0
        )
        content_cov = (
            sum(1 for it in items if str(it.get("content", "")).strip()) / total
            if total
            else 0.0
        )

        csv_values = [
            trade_date,
            platform,
            str(total),
            str(success),
            str(failure),
            f"{success_rate:.3f}",
            str(noise),
            f"{noise_rate:.3f}",
            f"{title_cov:.3f}",
            f"{time_cov:.3f}",
            f"{content_cov:.3f}",
        ]
        csv_lines.append(",".join(csv_values))

        md_lines.append(
            f"| {platform} | {total} | {success} | {failure} | {success_rate:.1%} | {noise_rate:.1%} | {title_cov:.1%} | {time_cov:.1%} | {content_cov:.1%} |"
        )

    # overall row
    total_all = len(rows_list)
    success_all = sum(
        1 for it in rows_list if str(it.get("capture_status", "")).lower() == "success"
    )
    failure_all = total_all - success_all
    success_rate_all = success_all / total_all if total_all else 0.0
    noise_all = sum(1 for it in rows_list if bool(it.get("is_noise")))
    noise_rate_all = noise_all / total_all if total_all else 0.0

    title_cov_all = (
        sum(1 for it in rows_list if str(it.get("title", "")).strip()) / total_all
        if total_all
        else 0.0
    )
    time_cov_all = (
        sum(1 for it in rows_list if str(it.get("post_time", "")).strip()) / total_all
        if total_all
        else 0.0
    )
    content_cov_all = (
        sum(1 for it in rows_list if str(it.get("content", "")).strip()) / total_all
        if total_all
        else 0.0
    )

    csv_lines.append(
        ",".join(
            [
                trade_date,
                "ALL",
                str(total_all),
                str(success_all),
                str(failure_all),
                f"{success_rate_all:.3f}",
                str(noise_all),
                f"{noise_rate_all:.3f}",
                f"{title_cov_all:.3f}",
                f"{time_cov_all:.3f}",
                f"{content_cov_all:.3f}",
            ]
        )
    )

    md_lines.append("")
    md_lines.append("## Totals")
    md_lines.append(f"- Total rows: {total_all}")
    md_lines.append(f"- Success: {success_all} ({success_rate_all:.1%})")
    md_lines.append(f"- Failures: {failure_all}")
    md_lines.append(f"- Noise: {noise_all} ({noise_rate_all:.1%})")
    md_lines.append(f"- Title coverage: {title_cov_all:.1%}")
    md_lines.append(f"- Time coverage: {time_cov_all:.1%}")
    md_lines.append(f"- Content coverage: {content_cov_all:.1%}")

    csv_path = target_dir / f"daily_summary_{trade_date}.csv"
    md_path = target_dir / f"daily_summary_{trade_date}.md"

    csv_path.write_text("\n".join(csv_lines), encoding="utf-8")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {"csv": csv_path, "md": md_path}
