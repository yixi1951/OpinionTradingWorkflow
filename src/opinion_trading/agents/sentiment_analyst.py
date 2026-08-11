"""Sentiment analyst: wraps the existing sentiment pipeline into the multi-agent format.

This bridges the legacy SentimentAnalysisSkill into a BaseAnalyst-compatible
interface so it can participate in the consensus engine alongside
technical and fundamental analysts.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Sequence

from opinion_trading.agents.analyst_base import AnalystOpinion, BaseAnalyst
from opinion_trading.core.log_utils import get_logger
from opinion_trading.core.models import AggregatedSentiment, OpinionSnapshot

logger = get_logger(__name__)


class SentimentAnalyst(BaseAnalyst):
    """Sentiment analysis agent wrapping the existing aggregation pipeline."""

    def __init__(
        self,
        aggregated: Dict[date, Dict[str, AggregatedSentiment]],
        snapshots: Sequence[OpinionSnapshot],
    ) -> None:
        """
        Args:
            aggregated: output of SentimentAnalysisSkill.aggregate()
            snapshots: raw opinion snapshots for metadata.
        """
        self._aggregated = aggregated
        self._snapshots = list(snapshots)

    @property
    def name(self) -> str:
        return "sentiment"

    def analyze(self, symbol: str, trade_date: date) -> AnalystOpinion | None:
        if trade_date not in self._aggregated:
            return None

        day_data = self._aggregated[trade_date]
        if symbol not in day_data:
            return None

        agg = day_data[symbol]
        score = float(agg.average_score)
        platform_scores = agg.platform_scores
        platform_weights = agg.platform_weights

        # Confidence based on number of platforms with data
        active_platforms = [p for p, s in platform_scores.items() if s != 0.0]
        n_platforms = len(active_platforms)
        base_conf = min(0.9, 0.3 + n_platforms * 0.12)

        # Add confidence if score is far from neutral
        abs_score = abs(score)
        if abs_score > 0.5:
            base_conf += 0.1
        elif abs_score > 0.3:
            base_conf += 0.05

        # Count posts
        total_posts = self._count_posts(symbol, trade_date)

        reasoning = self._build_reasoning(symbol, score, active_platforms, platform_scores, total_posts)

        return AnalystOpinion(
            symbol=symbol,
            trade_date=trade_date,
            analyst_name=self.name,
            score=max(-1.0, min(1.0, score)),
            confidence=min(0.95, base_conf),
            reasoning=reasoning,
            sub_scores={"platform_count": float(n_platforms), "total_posts": float(total_posts)},
            metadata={
                "platform_scores": {k: float(v) for k, v in platform_scores.items()},
                "platform_weights": {k: float(v) for k, v in platform_weights.items()},
                "n_platforms": n_platforms,
            },
        )

    def _count_posts(self, symbol: str, trade_date: date) -> int:
        return sum(
            1 for s in self._snapshots
            if s.symbol == symbol and s.trade_date == trade_date
        )

    def _build_reasoning(
        self,
        symbol: str,
        score: float,
        active_platforms: List[str],
        platform_scores: Dict[str, float],
        total_posts: int,
    ) -> str:
        parts = [f"{symbol} 情绪分析:"]

        if score > 0.3:
            parts.append(f"整体偏多 ({score:+.3f})")
        elif score < -0.3:
            parts.append(f"整体偏空 ({score:+.3f})")
        else:
            parts.append(f"中性 ({score:+.3f})")

        if active_platforms:
            platforms_str = ", ".join(
                f"{p}={platform_scores[p]:+.2f}" for p in active_platforms
            )
            parts.append(f"平台: {platforms_str}")
        parts.append(f"帖子数: {total_posts}")

        return " | ".join(parts)
