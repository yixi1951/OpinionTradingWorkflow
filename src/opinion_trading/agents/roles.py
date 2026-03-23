from __future__ import annotations

from datetime import date
from typing import Dict, List, Sequence, Tuple

from opinion_trading.core.models import AggregatedSentiment, OpinionSnapshot, PaperTrade, TradeSignal
from opinion_trading.skills.sentiment_analysis import SentimentAnalysisSkill
from opinion_trading.skills.sentiment_collection import SentimentCollectionSkill
from opinion_trading.skills.trade_simulation import PaperTradingSkill


class CollectorAgent:
    def __init__(self, skill: SentimentCollectionSkill) -> None:
        self.skill = skill

    def run(self, symbols: List[str], platforms: List[str], trade_date: date) -> List[OpinionSnapshot]:
        return self.skill.collect_for_days(symbols=symbols, platforms=platforms, trade_date=trade_date, lookback_days=1)


class AnalystAgent:
    def __init__(self, skill: SentimentAnalysisSkill) -> None:
        self.skill = skill

    def run(
        self,
        trade_date: date,
        snapshots: Sequence[OpinionSnapshot],
        platforms: Sequence[str],
    ) -> Tuple[List[TradeSignal], Dict[date, Dict[str, AggregatedSentiment]], List[str], Dict[str, float]]:
        aggregated = self.skill.aggregate(snapshots)
        best_combo, combo_scores = self.skill.rank_platform_combinations(
            current_date=trade_date,
            aggregated_by_date=aggregated,
            all_platforms=platforms,
        )
        signals = self.skill.generate_signals(
            current_date=trade_date,
            aggregated_by_date=aggregated,
            platforms=best_combo,
        )
        return signals, aggregated, best_combo, combo_scores


class TraderAgent:
    def __init__(self, skill: PaperTradingSkill) -> None:
        self.skill = skill

    def run(
        self,
        trade_date: date,
        signals: List[TradeSignal],
        today_aggregated: Dict[str, AggregatedSentiment],
        state: Dict,
    ) -> Tuple[List[PaperTrade], Dict]:
        return self.skill.simulate(
            trade_date=trade_date,
            signals=signals,
            today_aggregated=today_aggregated,
            state=state,
        )
