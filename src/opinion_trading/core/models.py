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
    consensus_score: float | None = None
    kelly_fraction: float | None = None
    analyst_scores: Dict[str, float] = field(default_factory=dict)
    analyst_confidences: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""

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
class AnalysisConfig:
    """Configuration for the multi-agent analysis pipeline."""

    enabled: bool = False
    min_analysts: int = 2
    bullish_threshold: float = 0.20
    bearish_threshold: float = -0.20
    sentiment_weight: float = 0.40
    technical_weight: float = 0.35
    fundamental_weight: float = 0.25
    max_kelly_fraction: float = 0.25
    min_confidence: float = 0.30
    technical_lookback_days: int = 365


@dataclass
class QualityConfig:
    """Raw data quality gates for sentiment confidence."""

    enabled: bool = True
    max_fallback_rate: float = 0.35
    max_noise_rate: float = 0.10
    fail_confidence_multiplier: float = 0.55
    block_signals_on_severe_failure: bool = True
    entity_match_rate_min: float = 0.70


@dataclass
class RiskConfig:
    """Unified risk limits (paper / future live)."""

    max_daily_loss_pct: float = 0.05
    max_single_symbol_notional_pct: float = 0.25
    max_open_positions: int = 10


@dataclass
class ExecutionConfig:
    """Signal export / paper broker (no live trading by default)."""

    mode: str = "paper"  # paper | export | simulation
    export_intents: bool = True
    dry_run: bool = True
    simulation_slippage_bps: float = 5.0


@dataclass
class SentimentRecencyConfig:
    """Time-decay weighting for posts (newer = higher weight)."""

    enabled: bool = True
    half_life_hours: float = 24.0


@dataclass
class WalkForwardConfig:
    enabled_in_evaluate: bool = True
    n_folds: int = 3
    train_days: int = 60
    test_days: int = 20


@dataclass
class RuntimeConfig:
    strategy: StrategyConfig
    symbols: List[str]
    memory_dir: str
    report_dir: str
    raw_dir: str
    scoring_mode: str = "hybrid"
    row_level_llm: bool = False
    max_posts: int = 20
    analysis: AnalysisConfig | None = None
    quality: QualityConfig | None = None
    execution: ExecutionConfig | None = None
    walk_forward: WalkForwardConfig | None = None
    risk: RiskConfig | None = None
    sentiment_recency: SentimentRecencyConfig | None = None
    explanation_lang: str = "zh"
