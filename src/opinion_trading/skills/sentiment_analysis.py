from __future__ import annotations

from collections import defaultdict
from datetime import date
from itertools import combinations
from typing import Dict, List, Sequence, Tuple

from opinion_trading.core.models import AggregatedSentiment, OpinionSnapshot, TradeSignal


class SentimentAnalysisSkill:
    def __init__(
        self,
        bearish_threshold: float,
        bullish_threshold: float,
        min_platforms_for_signal: int,
        reversal_min_delta: float,
    ) -> None:
        self.bearish_threshold = bearish_threshold
        self.bullish_threshold = bullish_threshold
        self.min_platforms_for_signal = min_platforms_for_signal
        self.reversal_min_delta = reversal_min_delta

    def aggregate(self, snapshots: Sequence[OpinionSnapshot]) -> Dict[date, Dict[str, AggregatedSentiment]]:
        grouped: Dict[date, Dict[str, Dict[str, List[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        for row in snapshots:
            grouped[row.trade_date][row.symbol][row.platform].append(row.sentiment_score)

        result: Dict[date, Dict[str, AggregatedSentiment]] = {}
        for trade_date, symbol_map in grouped.items():
            result[trade_date] = {}
            for symbol, platform_map in symbol_map.items():
                platform_scores = {
                    platform: sum(scores) / len(scores) for platform, scores in platform_map.items()
                }
                result[trade_date][symbol] = AggregatedSentiment(
                    trade_date=trade_date,
                    symbol=symbol,
                    platform_scores=platform_scores,
                )

        return result

    def generate_signals(
        self,
        current_date: date,
        aggregated_by_date: Dict[date, Dict[str, AggregatedSentiment]],
        platforms: Sequence[str],
    ) -> List[TradeSignal]:
        signals: List[TradeSignal] = []

        if current_date not in aggregated_by_date:
            return signals

        previous_dates = sorted([d for d in aggregated_by_date.keys() if d < current_date])
        prev_date = previous_dates[-1] if previous_dates else None

        for symbol, now_agg in aggregated_by_date[current_date].items():
            now_scores = now_agg.platform_scores
            now_bearish = [p for p in platforms if now_scores.get(p, 0.0) < self.bearish_threshold]
            now_bullish = [p for p in platforms if now_scores.get(p, 0.0) > self.bullish_threshold]

            if len(now_bullish) >= self.min_platforms_for_signal:
                confidence = min(0.99, 0.6 + 0.1 * len(now_bullish))
                signals.append(
                    TradeSignal(
                        trade_date=current_date,
                        symbol=symbol,
                        action="SELL",
                        confidence=confidence,
                        reason="Multi-platform extreme euphoria",
                        platforms=now_bullish,
                    )
                )
                continue

            if prev_date is None or symbol not in aggregated_by_date[prev_date]:
                continue

            prev_scores = aggregated_by_date[prev_date][symbol].platform_scores
            prev_bearish = [p for p in platforms if prev_scores.get(p, 0.0) < self.bearish_threshold]

            shared_bearish = [p for p in prev_bearish if p in platforms]
            if len(shared_bearish) < self.min_platforms_for_signal:
                continue

            deltas = [now_scores.get(p, prev_scores.get(p, 0.0)) - prev_scores.get(p, 0.0) for p in shared_bearish]
            avg_delta = sum(deltas) / len(deltas) if deltas else 0.0

            if avg_delta >= self.reversal_min_delta:
                confidence = min(0.99, 0.55 + avg_delta)
                signals.append(
                    TradeSignal(
                        trade_date=current_date,
                        symbol=symbol,
                        action="BUY",
                        confidence=confidence,
                        reason="Pessimism resonance reversal",
                        platforms=shared_bearish,
                    )
                )

        return signals

    def rank_platform_combinations(
        self,
        current_date: date,
        aggregated_by_date: Dict[date, Dict[str, AggregatedSentiment]],
        all_platforms: Sequence[str],
    ) -> Tuple[List[str], Dict[str, float]]:
        platform_scores: Dict[str, float] = {}
        best_combo: List[str] = list(all_platforms)
        best_score = float("-inf")

        for size in range(self.min_platforms_for_signal, len(all_platforms) + 1):
            for combo in combinations(all_platforms, size):
                combo_list = list(combo)
                combo_score = self._combo_quality_score(current_date, aggregated_by_date, combo_list)
                key = "+".join(combo_list)
                platform_scores[key] = combo_score
                if combo_score > best_score:
                    best_score = combo_score
                    best_combo = combo_list

        return best_combo, platform_scores

    def _combo_quality_score(
        self,
        current_date: date,
        aggregated_by_date: Dict[date, Dict[str, AggregatedSentiment]],
        platforms: Sequence[str],
    ) -> float:
        today = aggregated_by_date.get(current_date, {})
        if not today:
            return 0.0

        score_sum = 0.0
        count = 0
        for agg in today.values():
            values = [agg.platform_scores[p] for p in platforms if p in agg.platform_scores]
            if not values:
                continue
            resonance = max(values) - min(values)
            score_sum += abs(sum(values) / len(values)) - 0.2 * resonance
            count += 1

        return score_sum / count if count else 0.0
