"""Human-readable explanations for multi-agent consensus (mitigate black-box risk)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Dict, List, Sequence

from opinion_trading.core.models import AggregatedSentiment

if TYPE_CHECKING:
    from opinion_trading.agents.consensus_engine import ConsensusSignal


def build_consensus_explanation(
    signal: "ConsensusSignal",
    analyst_weights: Dict[str, float] | None = None,
    *,
    lang: str = "zh",
) -> str:
    """Structured explanation: weights, contributions, agreement, Kelly."""
    cfg_weights = analyst_weights or _normalized_weights_from_signal(signal)
    en = (lang or "zh").lower().startswith("en")
    if en:
        lines: List[str] = [
            f"[Multi-Agent] Consensus {signal.consensus_score:+.3f} → "
            f"{signal.consensus_direction} "
            f"(confidence {signal.confidence:.0%}, Kelly {signal.kelly_fraction:.1%})",
            f"Analysts {signal.n_analysts}, agreeing {signal.n_agreeing}.",
            "",
            "Contributions (score × weight × confidence, pre-normalize):",
        ]
        for name, op in sorted(signal.analyst_opinions.items()):
            w = cfg_weights.get(name, 1.0)
            contrib = op.score * w * op.confidence
            lines.append(
                f"  · {name}: score {op.score:+.3f}, conf {op.confidence:.2f}, "
                f"weight {w:.2f}, contrib ≈ {contrib:+.4f}"
            )
            if op.reasoning:
                snippet = op.reasoning.strip().replace("\n", " ")[:160]
                lines.append(
                    f"    Rationale: {snippet}{'…' if len(op.reasoning) > 160 else ''}"
                )
        lines.extend(_factor_diversity_note(signal, lang="en"))
        return "\n".join(lines)

    lines = [
        f"共识得分 {signal.consensus_score:+.3f} → {signal.consensus_direction} "
        f"(置信度 {signal.confidence:.0%}, Kelly 建议仓位 {signal.kelly_fraction:.1%})",
        f"参与分析师 {signal.n_analysts} 位，同向 {signal.n_agreeing} 位。",
        "",
        "分项贡献 (score × 配置权重 × 置信度，归一化前):",
    ]
    for name, op in sorted(signal.analyst_opinions.items()):
        w = cfg_weights.get(name, 1.0)
        contrib = op.score * w * op.confidence
        lines.append(
            f"  · {name}: 得分 {op.score:+.3f}, 置信 {op.confidence:.2f}, "
            f"权重 {w:.2f}, 贡献 ≈ {contrib:+.4f}"
        )
        if op.reasoning:
            snippet = op.reasoning.strip().replace("\n", " ")[:160]
            lines.append(f"    依据: {snippet}{'…' if len(op.reasoning) > 160 else ''}")
    lines.extend(_factor_diversity_note(signal, lang="zh"))
    return "\n".join(lines)


def build_consensus_explanation_dict(
    signal: "ConsensusSignal",
    analyst_weights: Dict[str, float] | None = None,
) -> Dict[str, object]:
    """Machine-readable explanation for JSONL / UI."""
    weights = analyst_weights or _normalized_weights_from_signal(signal)
    contributions: Dict[str, float] = {}
    for name, op in signal.analyst_opinions.items():
        w = weights.get(name, 1.0)
        contributions[name] = round(op.score * w * op.confidence, 6)

    return {
        "consensus_score": signal.consensus_score,
        "consensus_direction": signal.consensus_direction,
        "confidence": signal.confidence,
        "kelly_fraction": signal.kelly_fraction,
        "n_analysts": signal.n_analysts,
        "n_agreeing": signal.n_agreeing,
        "analyst_weights_used": weights,
        "contributions": contributions,
        "analyst_scores": {n: op.score for n, op in signal.analyst_opinions.items()},
        "analyst_confidences": {
            n: op.confidence for n, op in signal.analyst_opinions.items()
        },
        "text": build_consensus_explanation(signal, analyst_weights=weights),
    }


def _normalized_weights_from_signal(signal: "ConsensusSignal") -> Dict[str, float]:
    """Best-effort weights: equal if unknown."""
    names = list(signal.analyst_opinions.keys())
    if not names:
        return {}
    default = 1.0 / len(names)
    return {n: default for n in names}


def _factor_diversity_note(signal: "ConsensusSignal", *, lang: str = "zh") -> List[str]:
    names = set(signal.analyst_opinions.keys())
    en = (lang or "zh").lower().startswith("en")
    if len(names) >= 3:
        if en:
            return [
                "",
                "Multi-factor: sentiment, technical, and fundamental inputs reduce "
                "single-source bias.",
            ]
        return ["", "多因子: 情绪 + 技术 + 基本面均已参与，降低单一舆情因子依赖。"]
    missing = {"sentiment", "technical", "fundamental"} - names
    if missing:
        if en:
            return [
                "",
                f"Note: missing {', '.join(sorted(missing))} analyst output; "
                "consensus may lean on available factors.",
            ]
        return [
            "",
            f"注意: 缺少 {', '.join(sorted(missing))} 分析师输出，共识可能偏向可用因子。",
        ]
    return []


def build_sentiment_explanation(
    *,
    symbol: str,
    action: str,
    confidence: float,
    trigger_platforms: Sequence[str],
    agg: AggregatedSentiment | None,
    platform_weights: Dict[str, float],
    bullish_threshold: float,
    bearish_threshold: float,
    kelly_fraction: float | None = None,
    legacy_reason: str = "",
    lang: str = "zh",
) -> str:
    """Explain pure sentiment signals (no multi-agent consensus)."""
    en = (lang or "zh").lower().startswith("en")
    if en:
        lines: List[str] = [
            f"[Sentiment-only] {symbol} → {action} (confidence {confidence:.0%})",
        ]
        if kelly_fraction is not None and kelly_fraction > 0:
            lines.append(
                f"Kelly sizing {kelly_fraction:.1%} (paper trades / export intents)."
            )
        if legacy_reason:
            lines.append(f"Rule: {legacy_reason}")
        if agg is not None:
            lines.append(f"Weighted sentiment {agg.average_score:+.3f}.")
            lines.append(
                f"Thresholds: bullish > {bullish_threshold:+.2f}, "
                f"bearish < {bearish_threshold:+.2f}."
            )
            lines.append("Platform breakdown:")
            for p in trigger_platforms:
                sc = float(agg.platform_scores.get(p, 0.0))
                w = float(platform_weights.get(p, 1.0))
                lines.append(f"  · {p}: score {sc:+.3f}, weight {w:.2f}")
        else:
            lines.append(f"Platforms: {', '.join(trigger_platforms) or '—'}")
        lines.append("")
        lines.append(
            "Note: without multi-agent consensus, signals use platform aggregation only; "
            "set analysis.enabled in settings.yaml to add technical & fundamental factors."
        )
        return "\n".join(lines)

    lines = [
        f"[纯情绪] {symbol} → {action}（置信度 {confidence:.0%}）",
    ]
    if kelly_fraction is not None and kelly_fraction > 0:
        lines.append(f"Kelly 建议仓位 {kelly_fraction:.1%}（纸面/导出意图使用此比例）。")
    if legacy_reason:
        lines.append(f"规则: {legacy_reason}")

    if agg is not None:
        lines.append(f"加权综合舆情 {agg.average_score:+.3f}。")
        lines.append(
            f"阈值: 看多 > {bullish_threshold:+.2f}，看空 < {bearish_threshold:+.2f}。"
        )
        lines.append("触发平台分项:")
        for p in trigger_platforms:
            sc = float(agg.platform_scores.get(p, 0.0))
            w = float(platform_weights.get(p, 1.0))
            lines.append(f"  · {p}: 得分 {sc:+.3f}, 配置权重 {w:.2f}")
    else:
        lines.append(f"触发平台: {', '.join(trigger_platforms) or '—'}")

    lines.append("")
    lines.append(
        "说明: 未启用多 Agent 或未形成共识时，仅依据舆情平台组合与阈值；"
        "可在 settings.yaml 开启 analysis.enabled 以融合技术面与基本面。"
    )
    return "\n".join(lines)


def sentiment_kelly_from_confidence(
    confidence: float,
    *,
    max_kelly_fraction: float = 0.25,
) -> float:
    """Conservative Kelly proxy for sentiment-only signals."""
    edge = max(0.0, min(1.0, confidence))
    raw = edge * 0.35
    return max(0.0, min(max_kelly_fraction, raw))


def enrich_sentiment_trade_signals(
    signals: List,
    *,
    aggregated_today: Dict[str, AggregatedSentiment],
    platform_weights: Dict[str, float],
    bullish_threshold: float,
    bearish_threshold: float,
    max_kelly_fraction: float = 0.25,
    lang: str = "zh",
) -> None:
    """Mutates TradeSignal in place: explanation + kelly for sentiment-only rows."""
    from opinion_trading.core.models import TradeSignal

    for sig in signals:
        if not isinstance(sig, TradeSignal):
            continue
        if sig.explanation and (
            "共识得分" in sig.explanation
            or "[Multi-Agent]" in sig.explanation
            or "Consensus " in sig.explanation
        ):
            continue
        if (
            sig.kelly_fraction is not None
            and sig.explanation
            and ("[纯情绪]" in sig.explanation or "[Sentiment-only]" in sig.explanation)
        ):
            continue
        agg = aggregated_today.get(sig.symbol)
        kelly = sentiment_kelly_from_confidence(
            sig.confidence, max_kelly_fraction=max_kelly_fraction
        )
        sig.kelly_fraction = kelly
        sent_score = float(agg.average_score) if agg else 0.0
        sig.analyst_scores = {"sentiment": sent_score}
        sig.analyst_confidences = {"sentiment": sig.confidence}
        sig.explanation = build_sentiment_explanation(
            symbol=sig.symbol,
            action=sig.action,
            confidence=sig.confidence,
            trigger_platforms=sig.platforms,
            agg=agg,
            platform_weights=platform_weights,
            bullish_threshold=bullish_threshold,
            bearish_threshold=bearish_threshold,
            kelly_fraction=kelly,
            legacy_reason=sig.reason,
            lang=lang,
        )
        sig.reason = sig.explanation


def translate_signal_explanation_for_ui(
    text: str,
    lang: str,
    *,
    row: Dict[str, object] | None = None,
) -> str:
    """Re-localize stored pipeline explanations when UI language differs."""
    if not text or (lang or "zh").lower().startswith("zh"):
        return text
    if row and ("共识得分" in text or "[Multi-Agent]" in text):
        try:
            from opinion_trading.agents.analyst_base import AnalystOpinion
            from opinion_trading.agents.consensus_engine import ConsensusSignal

            scores = row.get("analyst_scores") or {}
            confs = row.get("analyst_confidences") or {}
            if not isinstance(scores, dict):
                scores = {}
            if not isinstance(confs, dict):
                confs = {}
            opinions = {}
            for name, sc in scores.items():
                opinions[str(name)] = AnalystOpinion(
                    analyst_name=str(name),
                    symbol=str(row.get("symbol", "")),
                    trade_date=date.today(),
                    score=float(sc),
                    confidence=float(confs.get(name, row.get("confidence", 0.5))),
                    direction="NEUTRAL",
                    reasoning="",
                )
            cs = ConsensusSignal(
                symbol=str(row.get("symbol", "")),
                trade_date=date.today(),
                consensus_score=float(
                    row.get("consensus_score", row.get("confidence", 0)) or 0
                ),
                consensus_direction=str(
                    row.get("consensus_direction", row.get("action", "NEUTRAL"))
                ),
                confidence=float(row.get("confidence", 0) or 0),
                kelly_fraction=float(row.get("kelly_fraction", 0) or 0),
                analyst_opinions=opinions,
                n_analysts=int(row.get("n_analysts", len(opinions)) or len(opinions)),
                n_agreeing=int(row.get("n_agreeing", 0) or 0),
            )
            return build_consensus_explanation(cs, lang="en")
        except (TypeError, ValueError, KeyError):
            pass

    if row and "[纯情绪]" in text:
        try:
            platforms = row.get("platforms") or []
            if isinstance(platforms, str):
                platforms = [platforms]
            return build_sentiment_explanation(
                symbol=str(row.get("symbol", "")),
                action=str(row.get("action", "")),
                confidence=float(row.get("confidence", 0) or 0),
                trigger_platforms=list(platforms),
                agg=None,
                platform_weights={},
                bullish_threshold=0.0,
                bearish_threshold=0.0,
                kelly_fraction=(
                    float(row["kelly_fraction"])
                    if row.get("kelly_fraction") is not None
                    else None
                ),
                legacy_reason=str(row.get("reason", "")),
                lang="en",
            )
        except (TypeError, ValueError):
            pass
    if "[纯情绪]" in text:
        return text.replace("[纯情绪]", "[Sentiment-only]", 1)
    if "共识得分" in text and "[Multi-Agent]" not in text:
        return "[Multi-Agent]\n" + text.replace("共识得分", "Consensus score", 1)
    return text
