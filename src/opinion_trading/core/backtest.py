from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from opinion_trading.core.config_loader import load_runtime_config
from opinion_trading.core.metrics import compute_performance_metrics
from opinion_trading.integrations.platform_sentiment_stub import (
    PlatformSentimentProvider,
)
from opinion_trading.skills.sentiment_analysis import SentimentAnalysisSkill
from opinion_trading.skills.sentiment_collection import SentimentCollectionSkill
from opinion_trading.skills.trade_simulation import PaperTradingSkill


@dataclass
class BacktestResult:
    bearish_threshold: float
    bullish_threshold: float
    platforms: List[str]
    annual_return: float
    max_drawdown: float
    sharpe: float
    final_equity: float


class StrategyBacktester:
    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        self.config = load_runtime_config(config_path)
        self.collector = SentimentCollectionSkill(PlatformSentimentProvider())

    def run_single(
        self,
        start_date: date,
        end_date: date,
        bearish_threshold: float,
        bullish_threshold: float,
        platforms: Sequence[str],
    ) -> BacktestResult:
        analysis = SentimentAnalysisSkill(
            bearish_threshold=bearish_threshold,
            bullish_threshold=bullish_threshold,
            min_platforms_for_signal=self.config.strategy.min_platforms_for_signal,
            reversal_min_delta=self.config.strategy.reversal_min_delta,
            platform_weights=self.config.strategy.platform_weights,
        )
        trader = PaperTradingSkill(
            initial_cash=self.config.strategy.initial_cash,
            position_size_ratio=self.config.strategy.position_size_ratio,
        )

        state: Dict = {"cash": self.config.strategy.initial_cash, "positions": {}}
        equity_curve: List[float] = []

        for d in self._date_range(start_date, end_date):
            snapshots = self.collector.collect_for_days(
                symbols=self.config.symbols,
                platforms=list(platforms),
                trade_date=d,
                lookback_days=1,
            )
            aggregated = analysis.aggregate(snapshots)
            signals = analysis.generate_signals(
                current_date=d,
                aggregated_by_date=aggregated,
                platforms=platforms,
            )
            today = aggregated.get(d, {})
            _, state = trader.simulate(
                trade_date=d,
                signals=signals,
                today_aggregated=today,
                state=state,
            )

            equity_curve.append(trader.portfolio_value(today, state))

        metrics = compute_performance_metrics(equity_curve)
        return BacktestResult(
            bearish_threshold=bearish_threshold,
            bullish_threshold=bullish_threshold,
            platforms=list(platforms),
            annual_return=metrics["annual_return"],
            max_drawdown=metrics["max_drawdown"],
            sharpe=metrics["sharpe"],
            final_equity=metrics["final_equity"],
        )

    def optimize(
        self,
        start_date: date,
        end_date: date,
        bearish_values: Sequence[float],
    ) -> List[BacktestResult]:
        results: List[BacktestResult] = []
        all_platforms = self.config.strategy.platforms

        for bearish_threshold in bearish_values:
            for size in range(
                self.config.strategy.min_platforms_for_signal, len(all_platforms) + 1
            ):
                for combo in combinations(all_platforms, size):
                    results.append(
                        self.run_single(
                            start_date=start_date,
                            end_date=end_date,
                            bearish_threshold=bearish_threshold,
                            bullish_threshold=self.config.strategy.bullish_threshold,
                            platforms=list(combo),
                        )
                    )

        results.sort(key=lambda x: x.sharpe, reverse=True)
        return results

    def save_results(self, results: Iterable[BacktestResult], file_path: str) -> None:
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        rows = list(results)
        with target.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "bearish_threshold",
                    "bullish_threshold",
                    "platforms",
                    "annual_return",
                    "max_drawdown",
                    "sharpe",
                    "final_equity",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row.bearish_threshold,
                        row.bullish_threshold,
                        "+".join(row.platforms),
                        round(row.annual_return, 6),
                        round(row.max_drawdown, 6),
                        round(row.sharpe, 6),
                        round(row.final_equity, 4),
                    ]
                )

    @staticmethod
    def parse_date(value: str) -> date:
        return datetime.strptime(value, "%Y-%m-%d").date()

    @staticmethod
    def _date_range(start_date: date, end_date: date) -> Iterable[date]:
        d = start_date
        while d <= end_date:
            yield d
            d += timedelta(days=1)
