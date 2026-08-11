"""Data-quality gates: down-weight or block signals when raw crawl quality fails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from opinion_trading.core.quality_report import QualityReportBuilder


@dataclass
class QualityGateResult:
    overall_pass: bool
    platform_pass: Dict[str, bool]
    noise_rate: float
    fallback_rate: float
    sentiment_confidence_multiplier: float
    block_new_signals: bool
    messages: List[str]


def evaluate_raw_quality(
    raw_rows: Iterable[Dict],
    *,
    min_rows_for_gate: int = 5,
    max_fallback_rate: float = 0.35,
    max_noise_rate: float = 0.25,
    fail_multiplier: float = 0.55,
) -> QualityGateResult:
    """Summarize raw posts and derive confidence multiplier for analysts."""
    rows = list(raw_rows)
    builder = QualityReportBuilder("data/reports")
    overall = builder._summarize(rows)
    per_platform = builder._summarize_by_platform(rows)

    total = len(rows)
    fallback = sum(
        1
        for r in rows
        if str(r.get("capture_status", "")).lower() in ("fallback", "failed", "error")
        or str(r.get("failure_reason", "")).strip()
    )
    fallback_rate = fallback / total if total else 0.0
    noise_rate = float(overall.get("noise_rate", 0.0))
    overall_pass = overall.get("status", 0.0) >= 0.5 and noise_rate <= max_noise_rate

    platform_pass = {
        p: builder._passes(
            s["title_coverage"],
            s["time_coverage"],
            s["content_coverage"],
            s["noise_rate"],
        )
        for p, s in per_platform.items()
    }

    messages: List[str] = []
    multiplier = 1.0
    block = False

    if total < min_rows_for_gate:
        messages.append(f"原始帖不足 {min_rows_for_gate} 条，置信度下调。")
        multiplier = min(multiplier, 0.75)

    if fallback_rate > max_fallback_rate:
        messages.append(
            f"Fallback/失败占比 {fallback_rate:.1%} > {max_fallback_rate:.0%}，情绪权重应谨慎。"
        )
        multiplier = min(multiplier, fail_multiplier)

    if noise_rate > max_noise_rate:
        messages.append(f"噪声率 {noise_rate:.1%} 超阈值 {max_noise_rate:.0%}。")
        multiplier = min(multiplier, fail_multiplier)
        block = noise_rate > max_noise_rate + 0.15

    if not overall_pass:
        messages.append("质量报告 Overall 未 PASS。")
        multiplier = min(multiplier, fail_multiplier)

    failed_platforms = [p for p, ok in platform_pass.items() if not ok]
    if failed_platforms:
        messages.append(f"未 PASS 平台: {', '.join(failed_platforms)}")

    return QualityGateResult(
        overall_pass=overall_pass and fallback_rate <= max_fallback_rate,
        platform_pass=platform_pass,
        noise_rate=noise_rate,
        fallback_rate=fallback_rate,
        sentiment_confidence_multiplier=round(multiplier, 4),
        block_new_signals=block,
        messages=messages,
    )


def apply_quality_to_sentiment_confidence(
    base_confidence: float, gate: Optional[QualityGateResult]
) -> float:
    if gate is None:
        return base_confidence
    return max(0.05, min(1.0, base_confidence * gate.sentiment_confidence_multiplier))
