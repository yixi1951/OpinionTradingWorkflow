"""Multi-agent consensus engine.

Collects opinions from all analyst agents (technical, fundamental, sentiment),
computes a weighted consensus score, and generates a unified trade signal
with Kelly-based position sizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from opinion_trading.agents.analyst_base import AnalystOpinion
from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ConsensusSignal:
    """Final fused signal from all analysts."""

    symbol: str
    trade_date: date
    consensus_score: float  # -1 to +1
    consensus_direction: str  # BUY / SELL / NEUTRAL
    confidence: float  # 0 to 1
    kelly_fraction: float  # fraction of capital to allocate (0 to 1)
    analyst_opinions: Dict[str, AnalystOpinion] = field(default_factory=dict)
    n_analysts: int = 0
    n_agreeing: int = 0

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "trade_date": self.trade_date.isoformat(),
            "consensus_score": self.consensus_score,
            "consensus_direction": self.consensus_direction,
            "confidence": self.confidence,
            "kelly_fraction": round(self.kelly_fraction, 4),
            "n_analysts": self.n_analysts,
            "n_agreeing": self.n_agreeing,
            "analyst_scores": {
                name: op.score for name, op in self.analyst_opinions.items()
            },
            "analyst_confidences": {
                name: op.confidence for name, op in self.analyst_opinions.items()
            },
        }


@dataclass
class ConsensusConfig:
    """Configuration for the consensus engine."""

    # Weights for each analyst type (applied to confidence-weighted scores)
    analyst_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "sentiment": 0.40,
            "technical": 0.35,
            "fundamental": 0.25,
        }
    )
    # Minimum number of analysts that must report for a consensus
    min_analysts: int = 2
    # Thresholds for signal generation
    bullish_threshold: float = 0.20
    bearish_threshold: float = -0.20
    # Kelly fraction cap (conservative: never bet more than 25%)
    max_kelly_fraction: float = 0.25
    # Minimum confidence to act on a signal
    min_confidence: float = 0.30
    # Whether to require sentiment analyst (legacy mode compat)
    require_sentiment: bool = False


class ConsensusEngine:
    """Fuses opinions from multiple analysts into a single tradable signal."""

    def __init__(self, config: Optional[ConsensusConfig] = None) -> None:
        self.config = config or ConsensusConfig()

    def compute_consensus(
        self,
        opinions: List[AnalystOpinion],
        trade_date: date,
    ) -> List[ConsensusSignal]:
        """Group opinions by symbol and compute per-symbol consensus."""
        # Group by symbol
        by_symbol: Dict[str, List[AnalystOpinion]] = {}
        for op in opinions:
            by_symbol.setdefault(op.symbol, []).append(op)

        results: List[ConsensusSignal] = []
        for symbol, sym_opinions in by_symbol.items():
            signal = self._fuse(symbol, trade_date, sym_opinions)
            if signal is not None:
                results.append(signal)
        return results

    def _fuse(
        self,
        symbol: str,
        trade_date: date,
        opinions: List[AnalystOpinion],
    ) -> ConsensusSignal | None:
        """Fuse multiple opinions for one symbol into a ConsensusSignal."""
        cfg = self.config

        # Check minimum analyst count
        if len(opinions) < cfg.min_analysts:
            logger.debug(
                "Consensus: %s has %d analysts (need %d)",
                symbol, len(opinions), cfg.min_analysts,
            )
            return None

        # Check if sentiment is required
        if cfg.require_sentiment and not any(
            op.analyst_name == "sentiment" for op in opinions
        ):
            logger.debug("Consensus: %s missing sentiment analyst", symbol)
            return None

        # Build opinion map
        opinion_map: Dict[str, AnalystOpinion] = {
            op.analyst_name: op for op in opinions
        }

        # Weighted consensus score
        total_weight = 0.0
        weighted_score = 0.0
        weighted_confidence = 0.0
        opinions_used = 0

        for op in opinions:
            w = cfg.analyst_weights.get(op.analyst_name, 1.0)
            weighted_score += op.score * w * op.confidence
            weighted_confidence += op.confidence * w
            total_weight += w
            opinions_used += 1

        if total_weight <= 0:
            return None

        consensus_score = max(-1.0, min(1.0, weighted_score / total_weight))
        avg_confidence = weighted_confidence / total_weight

        # Direction
        if consensus_score >= cfg.bullish_threshold:
            direction = "BUY"
        elif consensus_score <= cfg.bearish_threshold:
            direction = "SELL"
        else:
            direction = "NEUTRAL"

        # Count agreeing analysts (same direction as consensus)
        n_agreeing = sum(
            1 for op in opinions
            if (consensus_score >= 0 and op.score >= 0)
            or (consensus_score < 0 and op.score < 0)
        )

        # Kelly fraction
        kelly = self._kelly_fraction(
            consensus_score=consensus_score,
            confidence=avg_confidence,
            n_analysts=len(opinions),
            n_agreeing=n_agreeing,
        )

        # Overall confidence
        confidence = self._overall_confidence(
            avg_confidence=avg_confidence,
            n_analysts=len(opinions),
            n_agreeing=n_agreeing,
            consensus_score=consensus_score,
        )

        if confidence < cfg.min_confidence and direction != "NEUTRAL":
            direction = "NEUTRAL"

        return ConsensusSignal(
            symbol=symbol,
            trade_date=trade_date,
            consensus_score=round(consensus_score, 4),
            consensus_direction=direction,
            confidence=round(confidence, 4),
            kelly_fraction=round(kelly, 4),
            analyst_opinions=opinion_map,
            n_analysts=opinions_used,
            n_agreeing=n_agreeing,
        )

    def _kelly_fraction(
        self,
        consensus_score: float,
        confidence: float,
        n_analysts: int,
        n_agreeing: int,
    ) -> float:
        """Compute Kelly criterion fraction.

        Simplified: f* = (p * b - q) / b where:
        - p = probability of winning (confidence * agreement_rate)
        - q = 1 - p
        - b = odds ratio (derived from |score|)
        """
        agreement_rate = n_agreeing / max(n_analysts, 1)
        p = min(0.95, confidence * (0.5 + agreement_rate * 0.5))
        q = 1.0 - p
        # Interpret |score| as edge magnitude
        edge = abs(consensus_score)
        b = max(0.1, edge * 5)  # odds ratio

        if b <= 0:
            return 0.0

        k = (p * b - q) / b
        k = max(0.0, min(self.config.max_kelly_fraction, k))
        return k

    def _overall_confidence(
        self,
        avg_confidence: float,
        n_analysts: int,
        n_agreeing: int,
        consensus_score: float,
    ) -> float:
        """Overall confidence score incorporating agreement and signal strength."""
        agreement_ratio = n_agreeing / max(n_analysts, 1)

        # Agreement bonus
        if agreement_ratio >= 0.8:
            agreement_bonus = 0.15
        elif agreement_ratio >= 0.6:
            agreement_bonus = 0.05
        else:
            agreement_bonus = -0.1

        # Signal strength bonus
        abs_score = abs(consensus_score)
        if abs_score > 0.5:
            strength_bonus = 0.1
        elif abs_score > 0.3:
            strength_bonus = 0.05
        else:
            strength_bonus = 0.0

        final = avg_confidence + agreement_bonus + strength_bonus
        return max(0.0, min(1.0, final))
