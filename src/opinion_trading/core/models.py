from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Dict, List


@dataclass
class OpinionSnapshot:
    timestamp: datetime
    trade_date: date
    platform: str
    symbol: str
    sentiment_score: float
    post_count: int
    source: str

    def to_dict(self) -> Dict:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        payload["trade_date"] = self.trade_date.isoformat()
        return payload


@dataclass
class AggregatedSentiment:
    trade_date: date
    symbol: str
    platform_scores: Dict[str, float]

    @property
    def average_score(self) -> float:
        if not self.platform_scores:
            return 0.0
        return sum(self.platform_scores.values()) / len(self.platform_scores)


@dataclass
class TradeSignal:
    trade_date: date
    symbol: str
    action: str
    confidence: float
    reason: str
    platforms: List[str]

    def to_dict(self) -> Dict:
        payload = asdict(self)
        payload["trade_date"] = self.trade_date.isoformat()
        return payload


@dataclass
class PaperTrade:
    trade_date: date
    symbol: str
    action: str
    shares: int
    price: float
    cash_after: float
    note: str

    def to_dict(self) -> Dict:
        payload = asdict(self)
        payload["trade_date"] = self.trade_date.isoformat()
        return payload


@dataclass
class StrategyConfig:
    platforms: List[str]
    bearish_threshold: float
    bullish_threshold: float
    min_platforms_for_signal: int
    reversal_min_delta: float
    initial_cash: float
    position_size_ratio: float


@dataclass
class RuntimeConfig:
    strategy: StrategyConfig
    symbols: List[str]
    memory_dir: str
    report_dir: str
