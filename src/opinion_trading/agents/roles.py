from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from opinion_trading.core.data_quality import QualityGateResult

from opinion_trading.core.models import (
    AggregatedSentiment,
    AnalysisConfig,
    OpinionSnapshot,
    PaperTrade,
    TradeSignal,
)
from opinion_trading.skills.sentiment_analysis import SentimentAnalysisSkill
from opinion_trading.skills.sentiment_collection import SentimentCollectionSkill
from opinion_trading.skills.trade_simulation import PaperTradingSkill


class CollectorAgent:
    def __init__(self, skill: SentimentCollectionSkill) -> None:
        self.skill = skill

    def run(
        self, symbols: List[str], platforms: List[str], trade_date: date
    ) -> List[OpinionSnapshot]:
        return self.skill.collect_for_days(
            symbols=symbols, platforms=platforms, trade_date=trade_date, lookback_days=1
        )


class SentimentAnalystAgent:
    """Expanded analyst that still exposes the original sentiment pipeline."""

    def __init__(self, skill: SentimentAnalysisSkill) -> None:
        self.skill = skill

    def run(
        self,
        trade_date: date,
        snapshots: Sequence[OpinionSnapshot],
        platforms: Sequence[str],
    ) -> Tuple[
        List[TradeSignal],
        Dict[date, Dict[str, AggregatedSentiment]],
        List[str],
        Dict[str, float],
    ]:
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


class MultiAnalystAgent:
    """Multi-agent scoring that fuses sentiment + technical + fundamental."""

    def __init__(
        self,
        sentiment_analyst: SentimentAnalystAgent,
        analysis_cfg: Optional[AnalysisConfig] = None,
        explanation_lang: str = "zh",
    ) -> None:
        self._sentiment_analyst = sentiment_analyst
        self._analysis_cfg = analysis_cfg or AnalysisConfig()
        self._explanation_lang = explanation_lang or "zh"
        self._technical_analyst: Optional["TechnicalAnalyst"] = None  # noqa: F821
        self._fundamental_analyst: Optional["FundamentalAnalyst"] = None  # noqa: F821
        self._consensus_engine: Optional["ConsensusEngine"] = None  # noqa: F821

    def _lazy_init(self) -> None:
        if self._technical_analyst is not None:
            return
        # Lazy imports to avoid circular dependencies
        from opinion_trading.agents.technical_analyst import TechnicalAnalyst
        from opinion_trading.agents.fundamental_analyst import FundamentalAnalyst
        from opinion_trading.agents.consensus_engine import (
            ConsensusEngine,
            ConsensusConfig,
        )

        self._technical_analyst = TechnicalAnalyst(
            lookback_days=self._analysis_cfg.technical_lookback_days,
        )
        self._fundamental_analyst = FundamentalAnalyst()

        cfg = ConsensusConfig(
            analyst_weights={
                "sentiment": self._analysis_cfg.sentiment_weight,
                "technical": self._analysis_cfg.technical_weight,
                "fundamental": self._analysis_cfg.fundamental_weight,
            },
            min_analysts=self._analysis_cfg.min_analysts,
            bullish_threshold=self._analysis_cfg.bullish_threshold,
            bearish_threshold=self._analysis_cfg.bearish_threshold,
            max_kelly_fraction=self._analysis_cfg.max_kelly_fraction,
            min_confidence=self._analysis_cfg.min_confidence,
        )
        self._consensus_engine = ConsensusEngine(cfg)

    def run(
        self,
        trade_date: date,
        snapshots: Sequence[OpinionSnapshot],
        platforms: Sequence[str],
        quality_gate: Optional["QualityGateResult"] = None,
    ) -> Tuple[
        List[TradeSignal],
        Dict[date, Dict[str, AggregatedSentiment]],
        List[str],
        Dict[str, float],
    ]:
        # 1. Run sentiment pipeline (always needed)
        aggregated = self._sentiment_analyst.skill.aggregate(snapshots)
        best_combo, combo_scores = self._sentiment_analyst.skill.rank_platform_combinations(
            current_date=trade_date,
            aggregated_by_date=aggregated,
            all_platforms=platforms,
        )

        # 2. Run multi-agent consensus
        self._lazy_init()

        # Collect opinions from all analysts
        aggregated.get(trade_date, {})
        opinions = []

        from opinion_trading.core.data_quality import apply_quality_to_sentiment_confidence

        for symbol in self._get_symbols(aggregated, trade_date):
            # Sentiment opinion
            from opinion_trading.agents.sentiment_analyst import SentimentAnalyst
            sent_analyst = SentimentAnalyst(aggregated, snapshots)
            sent_op = sent_analyst.analyze(symbol, trade_date)
            if sent_op is not None:
                if quality_gate is not None:
                    sent_op.confidence = apply_quality_to_sentiment_confidence(
                        sent_op.confidence, quality_gate
                    )
                opinions.append(sent_op)

            # Technical opinion
            if self._technical_analyst is not None:
                tech_op = self._technical_analyst.analyze(symbol, trade_date)
                if tech_op is not None:
                    opinions.append(tech_op)

            # Fundamental opinion
            if self._fundamental_analyst is not None:
                fund_op = self._fundamental_analyst.analyze(symbol, trade_date)
                if fund_op is not None:
                    opinions.append(fund_op)

        # 3. Compute consensus (will fall back gracefully if not enough analysts)
        consensus_signals: List = []
        if self._consensus_engine is not None and len(opinions) >= self._analysis_cfg.min_analysts:
            consensus_signals = self._consensus_engine.compute_consensus(opinions, trade_date)

        # 4. Generate TradeSignals from consensus (or fall back to pure sentiment)
        if consensus_signals:
            signals = self._consensus_to_trade_signals(consensus_signals, trade_date)
        else:
            # Fallback: pure sentiment signals
            signals = self._sentiment_analyst.skill.generate_signals(
                current_date=trade_date,
                aggregated_by_date=aggregated,
                platforms=best_combo,
            )
            from opinion_trading.core.explainability import enrich_sentiment_trade_signals

            skill = self._sentiment_analyst.skill
            enrich_sentiment_trade_signals(
                signals,
                aggregated_today=aggregated.get(trade_date, {}),
                platform_weights=skill.platform_weights,
                bullish_threshold=skill.bullish_threshold,
                bearish_threshold=skill.bearish_threshold,
                max_kelly_fraction=self._analysis_cfg.max_kelly_fraction,
                lang=self._explanation_lang,
            )

        if quality_gate is not None and quality_gate.block_new_signals:
            signals = []
        elif quality_gate is not None and quality_gate.sentiment_confidence_multiplier < 1.0:
            for sig in signals:
                sig.confidence = apply_quality_to_sentiment_confidence(
                    sig.confidence, quality_gate
                )

        return signals, aggregated, best_combo, combo_scores

    def _get_symbols(
        self,
        aggregated: Dict[date, Dict[str, AggregatedSentiment]],
        trade_date: date,
    ) -> List[str]:
        day_data = aggregated.get(trade_date, {})
        return list(day_data.keys())

    def _consensus_to_trade_signals(
        self,
        consensus_signals: List,
        trade_date: date,
    ) -> List[TradeSignal]:
        """Convert ConsensusSignal → TradeSignal for the downstream pipeline."""
        from opinion_trading.core.explainability import build_consensus_explanation

        weights = {
            "sentiment": self._analysis_cfg.sentiment_weight,
            "technical": self._analysis_cfg.technical_weight,
            "fundamental": self._analysis_cfg.fundamental_weight,
        }
        signals: List[TradeSignal] = []
        for cs in consensus_signals:
            if cs.consensus_direction == "NEUTRAL":
                continue
            explanation = build_consensus_explanation(
                cs, analyst_weights=weights, lang=self._explanation_lang
            )
            signals.append(
                TradeSignal(
                    trade_date=trade_date,
                    symbol=cs.symbol,
                    action=cs.consensus_direction,
                    confidence=cs.confidence,
                    reason=explanation,
                    platforms=list(cs.analyst_opinions.keys()),
                    consensus_score=cs.consensus_score,
                    kelly_fraction=cs.kelly_fraction,
                    analyst_scores={
                        n: float(op.score) for n, op in cs.analyst_opinions.items()
                    },
                    analyst_confidences={
                        n: float(op.confidence)
                        for n, op in cs.analyst_opinions.items()
                    },
                    explanation=explanation,
                )
            )
        return signals


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
