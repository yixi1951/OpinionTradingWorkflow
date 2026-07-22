"""Data quality monitor with threshold alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from opinion_trading.core.alert_notifier import AlertNotifier
from opinion_trading.core.semantic_enrichment import semantic_quality_stats


@dataclass
class QualityMonitorResult:
    trade_date: str
    metrics: Dict[str, float]
    alerts: List[str] = field(default_factory=list)
    ok: bool = True


DEFAULT_THRESHOLDS = {
    "title_coverage": 0.95,
    "time_coverage": 0.90,
    "content_coverage": 0.85,
    "noise_rate_max": 0.10,  # target <= 10%
    "entity_match_rate_min": 0.70,
    "fallback_rate_max": 0.35,
}


def _coverage(rows: List[Dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    ok = sum(1 for r in rows if str(r.get(key, "")).strip())
    return ok / len(rows)


def evaluate_quality_monitor(
    rows: List[Dict[str, Any]],
    *,
    trade_date: str,
    thresholds: Optional[Dict[str, float]] = None,
) -> QualityMonitorResult:
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    total = len(rows)
    noise = sum(1 for r in rows if bool(r.get("is_noise")))
    fallback = sum(
        1
        for r in rows
        if str(r.get("capture_status", "")).lower() in {"fallback", "failed", "error"}
    )
    sem = semantic_quality_stats(rows)
    metrics = {
        "rows": float(total),
        "title_coverage": _coverage(rows, "title"),
        "time_coverage": _coverage(rows, "post_time"),
        "content_coverage": _coverage(rows, "content"),
        "noise_rate": noise / total if total else 0.0,
        "fallback_rate": fallback / total if total else 0.0,
        "entity_match_rate": float(sem.get("entity_match_rate", 0.0)),
        "high_authority_rate": float(sem.get("high_authority_rate", 0.0)),
    }
    alerts: List[str] = []
    if metrics["title_coverage"] < thr["title_coverage"]:
        alerts.append(f"title_coverage {metrics['title_coverage']:.1%} < {thr['title_coverage']:.0%}")
    if metrics["time_coverage"] < thr["time_coverage"]:
        alerts.append(f"time_coverage {metrics['time_coverage']:.1%} < {thr['time_coverage']:.0%}")
    if metrics["content_coverage"] < thr["content_coverage"]:
        alerts.append(
            f"content_coverage {metrics['content_coverage']:.1%} < {thr['content_coverage']:.0%}"
        )
    if metrics["noise_rate"] > thr["noise_rate_max"]:
        alerts.append(f"noise_rate {metrics['noise_rate']:.1%} > {thr['noise_rate_max']:.0%}")
    if metrics["entity_match_rate"] < thr["entity_match_rate_min"]:
        alerts.append(
            f"entity_match_rate {metrics['entity_match_rate']:.1%} < {thr['entity_match_rate_min']:.0%}"
        )
    if metrics["fallback_rate"] > thr["fallback_rate_max"]:
        alerts.append(
            f"fallback_rate {metrics['fallback_rate']:.1%} > {thr['fallback_rate_max']:.0%}"
        )
    return QualityMonitorResult(
        trade_date=trade_date,
        metrics=metrics,
        alerts=alerts,
        ok=not alerts,
    )


def persist_and_alert(
    result: QualityMonitorResult,
    *,
    report_dir: str = "data/reports",
    notify: bool = True,
) -> str:
    path = Path(report_dir)
    path.mkdir(parents=True, exist_ok=True)
    target = path / f"quality_monitor_{result.trade_date}.md"
    lines = [
        f"# Quality Monitor - {result.trade_date}",
        "",
        f"- Status: {'PASS' if result.ok else 'ALERT'}",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Metrics",
    ]
    for k, v in result.metrics.items():
        if k == "rows":
            lines.append(f"- {k}: {int(v)}")
        else:
            lines.append(f"- {k}: {v:.2%}")
    lines.append("")
    lines.append("## Alerts")
    if result.alerts:
        for a in result.alerts:
            lines.append(f"- {a}")
    else:
        lines.append("- none")
    target.write_text("\n".join(lines), encoding="utf-8")

    if notify and result.alerts:
        notifier = AlertNotifier()
        notifier.push_alert(
            {
                "symbol": "QUALITY",
                "severity": "red",
                "direction": "down",
                "delta": result.metrics.get("noise_rate", 0.0),
                "previous_score": 0.0,
                "current_score": result.metrics.get("entity_match_rate", 0.0),
                "time": datetime.now().isoformat(timespec="seconds"),
            }
        )
    return str(target)
