from __future__ import annotations

from dataclasses import dataclass, asdict, field
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
class RawPostRecord:
    trade_date: date
    platform: str
    symbol: str
    title: str
    summary: str
    post_time: str
    content: str
    url: str
    source_page: str
    fetch_time: datetime
    is_noise: bool
    capture_status: str
    failure_reason: str

    def to_dict(self) -> Dict:
        payload = asdict(self)
        payload["trade_date"] = self.trade_date.isoformat()
        payload["fetch_time"] = self.fetch_time.isoformat()
        return payload


@dataclass
class AggregatedSentiment:
    trade_date: date
    symbol: str
    platform_scores: Dict[str, float]
    platform_weights: Dict[str, float] = field(default_factory=dict)

    @property
    def average_score(self) -> float:
        if not self.platform_scores:
            return 0.0
        if not self.platform_weights:
            return sum(self.platform_scores.values()) / len(self.platform_scores)

        weighted_sum = 0.0
        weight_total = 0.0
        for platform, score in self.platform_scores.items():
            weight = float(self.platform_weights.get(platform, 1.0))
            weighted_sum += float(score) * weight
            weight_total += weight

        if weight_total <= 0:
            return sum(self.platform_scores.values()) / len(self.platform_scores)
        return weighted_sum / weight_total


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
    platform_weights: Dict[str, float]
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
    raw_dir: str
