from __future__ import annotations

from datetime import date, datetime
from typing import Dict

from opinion_trading.agents.roles import AnalystAgent, CollectorAgent, TraderAgent
from opinion_trading.core.config_loader import load_runtime_config
from opinion_trading.core.memory_store import JsonLineMemoryStore
from opinion_trading.core.report_builder import DailyReportBuilder
from opinion_trading.integrations.platform_sentiment_stub import PlatformSentimentProvider
from opinion_trading.skills.sentiment_analysis import SentimentAnalysisSkill
from opinion_trading.skills.sentiment_collection import SentimentCollectionSkill
from opinion_trading.skills.trade_simulation import PaperTradingSkill


class OpinionTradingWorkflow:
    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        self.config = load_runtime_config(config_path)
        self.store = JsonLineMemoryStore(self.config.memory_dir)
        self.reporter = DailyReportBuilder(self.config.report_dir)

        collector_skill = SentimentCollectionSkill(PlatformSentimentProvider())
        analyst_skill = SentimentAnalysisSkill(
            bearish_threshold=self.config.strategy.bearish_threshold,
            bullish_threshold=self.config.strategy.bullish_threshold,
            min_platforms_for_signal=self.config.strategy.min_platforms_for_signal,
            reversal_min_delta=self.config.strategy.reversal_min_delta,
        )
        trader_skill = PaperTradingSkill(
            initial_cash=self.config.strategy.initial_cash,
            position_size_ratio=self.config.strategy.position_size_ratio,
        )

        self.collector = CollectorAgent(collector_skill)
        self.analyst = AnalystAgent(analyst_skill)
        self.trader = TraderAgent(trader_skill)

    def run_daily(self, run_date: date) -> Dict:
        snapshots = self.collector.run(
            symbols=self.config.symbols,
            platforms=self.config.strategy.platforms,
            trade_date=run_date,
        )
        self.store.append_many("sentiment_history.jsonl", [x.to_dict() for x in snapshots])

        signals, aggregated, best_combo, combo_scores = self.analyst.run(
            trade_date=run_date,
            snapshots=snapshots,
            platforms=self.config.strategy.platforms,
        )
        self.store.append_many("signal_history.jsonl", [x.to_dict() for x in signals])

        state = self.store.load_state()
        today_aggregated = aggregated.get(run_date, {})
        trades, updated_state = self.trader.run(
            trade_date=run_date,
            signals=signals,
            today_aggregated=today_aggregated,
            state=state,
        )

        self.store.append_many("trade_history.jsonl", [x.to_dict() for x in trades])
        self.store.save_state(updated_state)

        report_path = self.reporter.build(
            trade_date=run_date.isoformat(),
            best_platform_combo=best_combo,
            combo_scores=combo_scores,
            aggregated_today=today_aggregated,
            signals=signals,
            trades=trades,
            state=updated_state,
        )

        return {
            "run_time": datetime.now().isoformat(),
            "run_date": run_date.isoformat(),
            "signals": len(signals),
            "trades": len(trades),
            "report": str(report_path),
            "best_combo": best_combo,
            "state": updated_state,
        }
