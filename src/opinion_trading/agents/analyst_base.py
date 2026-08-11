"""Abstract base class for all analyst agents in the multi-agent scoring system.

Each analyst produces an independent score (-1 to +1) for a symbol,
along with confidence and explanatory text.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List


@dataclass
class AnalystOpinion:
    """Structured output from a single analyst agent."""

    symbol: str
    trade_date: date
    analyst_name: str
    score: float  # -1 to +1
    confidence: float  # 0 to 1
    reasoning: str  # human-readable explanation
    sub_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "trade_date": self.trade_date.isoformat(),
            "analyst_name": self.analyst_name,
            "score": self.score,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "sub_scores": self.sub_scores,
            "metadata": {k: str(v) for k, v in self.metadata.items()},
        }


class BaseAnalyst(ABC):
    """Override `analyze()` to produce a signal for one symbol."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable analyst name (e.g. 'technical', 'fundamental')."""
        ...

    @abstractmethod
    def analyze(self, symbol: str, trade_date: date) -> AnalystOpinion | None:
        """Analyze a single symbol and return opinion, or None if unavailable."""
        ...

    def analyze_batch(
        self, symbols: List[str], trade_date: date
    ) -> List[AnalystOpinion]:
        """Analyze multiple symbols. Default: sequential single analysis."""
        results: List[AnalystOpinion] = []
        for sym in symbols:
            try:
                opinion = self.analyze(sym, trade_date)
                if opinion is not None:
                    results.append(opinion)
            except Exception as exc:
                from opinion_trading.core.log_utils import get_logger
                get_logger(__name__).warning(
                    "%s analyst failed for %s: %s", self.name, sym, exc
                )
        return results
