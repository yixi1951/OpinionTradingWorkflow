"""Multi-agent backtester — runs pure-sentiment vs multi-agent consensus comparison.

Reads historical signal data from ``signal_history.jsonl``, optionally fetches
market data for technical / fundamental analysts on each backtest date, and
produces comparative evaluation metrics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

from opinion_trading.agents.analyst_base import AnalystOpinion
from opinion_trading.agents.consensus_engine import (
    ConsensusConfig,
    ConsensusEngine,
)
from opinion_trading.agents.fundamental_analyst import FundamentalAnalyst
from opinion_trading.agents.sentiment_analyst import SentimentAnalyst
from opinion_trading.agents.technical_analyst import TechnicalAnalyst
from opinion_trading.core.config_loader import load_runtime_config
from opinion_trading.core.evaluation import EvalSummary, evaluate_signals
from opinion_trading.core.log_utils import get_logger
from opinion_trading.core.models import (
    AggregatedSentiment,
    AnalysisConfig,
    OpinionSnapshot,
)

logger = get_logger(__name__)


@dataclass
class MultiAgentBacktestResult:
    """Result of one backtest run (either pure-sentiment or multi-agent)."""

    mode: str  # "sentiment_only" or "multi_agent"
    eval_summary: EvalSummary
    total_dates: int
    total_signals: int
    details: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class BacktestComparison:
    """Side-by-side comparison of sentiment-only vs multi-agent."""

    sentiment: MultiAgentBacktestResult
    multi_agent: MultiAgentBacktestResult
    start_date: date
    end_date: date
    symbols: List[str]


class MultiAgentBacktester:
    """Backtester that can run both pure-sentiment and multi-agent strategies."""

    def __init__(
        self,
        config_path: str = "config/settings.yaml",
        signal_path: str = "data/memory/signal_history.jsonl",
        analysis_cfg: Optional[AnalysisConfig] = None,
    ) -> None:
        self.config = load_runtime_config(config_path)
        self.signal_path = Path(signal_path)
        self.analysis_cfg = analysis_cfg or AnalysisConfig()

        # Lazy-init analysts
        self._technical_analyst: Optional[TechnicalAnalyst] = None
        self._fundamental_analyst: Optional[FundamentalAnalyst] = None
        self._consensus_engine: Optional[ConsensusEngine] = None

    def _lazy_init_analysts(self) -> None:
        if self._technical_analyst is not None:
            return
        self._technical_analyst = TechnicalAnalyst(
            lookback_days=self.analysis_cfg.technical_lookback_days,
        )
        self._fundamental_analyst = FundamentalAnalyst()
        consensus_cfg = ConsensusConfig(
            analyst_weights={
                "sentiment": self.analysis_cfg.sentiment_weight,
                "technical": self.analysis_cfg.technical_weight,
                "fundamental": self.analysis_cfg.fundamental_weight,
            },
            min_analysts=self.analysis_cfg.min_analysts,
            bullish_threshold=self.analysis_cfg.bullish_threshold,
            bearish_threshold=self.analysis_cfg.bearish_threshold,
            max_kelly_fraction=self.analysis_cfg.max_kelly_fraction,
            min_confidence=self.analysis_cfg.min_confidence,
            require_sentiment=False,
        )
        self._consensus_engine = ConsensusEngine(config=consensus_cfg)

    # ------------------------------------------------------------------
    # Load historical sentiment + price data
    # ------------------------------------------------------------------

    def load_signal_history(self) -> pd.DataFrame:
        """Load signal_history.jsonl as a DataFrame with clean dtypes."""
        if not self.signal_path.exists():
            logger.warning("Signal history not found at %s", self.signal_path)
            return pd.DataFrame()

        rows: List[Dict] = []
        for line in self.signal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        if "confidence" in df.columns:
            df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(
                0.0
            )
        return df

    def load_historical_aggregated(
        self, start_date: date, end_date: date
    ) -> Dict[date, Dict[str, AggregatedSentiment]]:
        """Rebuild aggregated sentiment dict from signal history.

        Returns a dict keyed by trade_date → {symbol: AggregatedSentiment}
        with best-effort sentiment_score fields.
        """
        df = self.load_signal_history()
        if df.empty:
            return {}

        df = df[
            (df["trade_date"] >= pd.Timestamp(start_date))
            & (df["trade_date"] <= pd.Timestamp(end_date))
        ]
        result: Dict[date, Dict[str, AggregatedSentiment]] = {}
        for trade_dt, group in df.groupby("trade_date"):
            d = trade_dt.date()
            inner: Dict[str, AggregatedSentiment] = {}
            for _, row in group.iterrows():
                sym = str(row.get("symbol", ""))
                if not sym:
                    continue
                score = float(row.get("score", row.get("consensus_score", 0.0)))
                float(row.get("confidence", 0.0))
                inner[sym] = AggregatedSentiment(
                    trade_date=d,
                    symbol=sym,
                    platform_scores={"history": score},
                    platform_weights=self.config.strategy.platform_weights,
                )
            result[d] = inner
        return result

    # ------------------------------------------------------------------
    # Run comparison
    # ------------------------------------------------------------------

    def run_comparison(
        self,
        start_date: date,
        end_date: date,
        price_df: pd.DataFrame,
    ) -> BacktestComparison:
        """Run both pure-sentiment and multi-agent backtests and compare."""
        symbols = sorted(
            {s.strip() for s in (self.config.symbols or []) if s.strip()}
        )

        logger.info(
            "Running comparison backtest: %s → %s, %d symbols",
            start_date, end_date, len(symbols),
        )

        # 1. Pure sentiment backtest
        sent_result = self._run_sentiment_only(start_date, end_date, price_df, symbols)

        # 2. Multi-agent backtest
        ma_result = self._run_multi_agent(start_date, end_date, price_df, symbols)

        return BacktestComparison(
            sentiment=sent_result,
            multi_agent=ma_result,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
        )

    def _run_sentiment_only(
        self,
        start_date: date,
        end_date: date,
        price_df: pd.DataFrame,
        symbols: Sequence[str],
    ) -> MultiAgentBacktestResult:
        """Backtest using only sentiment signals from signal_history.jsonl."""
        df = self.load_signal_history()
        if df.empty:
            return MultiAgentBacktestResult(
                mode="sentiment_only",
                eval_summary=EvalSummary(0, 0.0, 0.0, 0.0, 0.0),
                total_dates=0,
                total_signals=0,
            )

        df = df[
            (df["trade_date"] >= pd.Timestamp(start_date))
            & (df["trade_date"] <= pd.Timestamp(end_date))
        ].copy()

        if df.empty:
            return MultiAgentBacktestResult(
                mode="sentiment_only",
                eval_summary=EvalSummary(0, 0.0, 0.0, 0.0, 0.0),
                total_dates=0,
                total_signals=0,
            )

        # Convert to standard signal format for evaluation
        merged, summary = evaluate_signals(
            df, price_df,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        # Count unique dates and signals
        total_dates = int(df["trade_date"].nunique()) if "trade_date" in df else 0
        total_signals = summary.total_signals

        return MultiAgentBacktestResult(
            mode="sentiment_only",
            eval_summary=summary,
            total_dates=total_dates,
            total_signals=total_signals,
            details=merged,
        )

    def _run_multi_agent(
        self,
        start_date: date,
        end_date: date,
        price_df: pd.DataFrame,
        symbols: Sequence[str],
    ) -> MultiAgentBacktestResult:
        """Backtest using multi-agent consensus (sentiment + technical + fundamental)."""
        self._lazy_init_analysts()
        assert self._technical_analyst is not None
        assert self._fundamental_analyst is not None
        assert self._consensus_engine is not None

        # Load historical sentiment data per symbol per date
        hist_df = self.load_signal_history()

        all_rows: List[Dict] = []
        current = start_date
        while current <= end_date:
            # ── Get sentiment for this date ──
            sentiment_data = self._get_date_sentiment(hist_df, current, symbols)

            # Build SentimentAnalyst instance for this date
            sentiment_opinions: List[AnalystOpinion] = []
            if sentiment_data:
                snapshots, aggregated_by_date = sentiment_data
                sent_analyst = SentimentAnalyst(
                    aggregated=aggregated_by_date,
                    snapshots=snapshots,
                )
                sent_opinions = sent_analyst.analyze_batch(list(symbols), current)
                sentiment_opinions = [o for o in sent_opinions if o is not None]

            # ── Technical analyst ──
            tech_opinions: List[AnalystOpinion] = []
            for sym in symbols:
                op = self._technical_analyst.analyze(str(sym), current)
                if op is not None:
                    tech_opinions.append(op)

            # ── Fundamental analyst ──
            fund_opinions: List[AnalystOpinion] = []
            for sym in symbols:
                op = self._fundamental_analyst.analyze(str(sym), current)
                if op is not None:
                    fund_opinions.append(op)

            # ── Consensus ──
            all_opinions = sentiment_opinions + tech_opinions + fund_opinions
            if all_opinions:
                signals = self._consensus_engine.compute_consensus(
                    all_opinions, current
                )
                for sig in signals:
                    row = {
                        "trade_date": current.isoformat(),
                        "symbol": sig.symbol,
                        "action": sig.consensus_direction,
                        "confidence": sig.confidence,
                        "consensus_score": sig.consensus_score,
                        "kelly_fraction": sig.kelly_fraction,
                        "n_analysts": sig.n_analysts,
                        "n_agreeing": sig.n_agreeing,
                        "analyst_scores": json.dumps(
                            sig.to_dict().get("analyst_scores", {})
                        ),
                        "analyst_confidences": json.dumps(
                            sig.to_dict().get("analyst_confidences", {})
                        ),
                        "reason": (
                            f"Multi-agent consensus: {sig.n_analysts} analysts, "
                            f"{sig.n_agreeing} agreeing, score={sig.consensus_score:+.3f}, "
                            f"kelly={sig.kelly_fraction:.2%}"
                        ),
                    }
                    all_rows.append(row)

            current += timedelta(days=1)

        if not all_rows:
            return MultiAgentBacktestResult(
                mode="multi_agent",
                eval_summary=EvalSummary(0, 0.0, 0.0, 0.0, 0.0),
                total_dates=0,
                total_signals=0,
            )

        signal_df = pd.DataFrame(all_rows)
        signal_df["trade_date"] = pd.to_datetime(signal_df["trade_date"], errors="coerce")

        merged, summary = evaluate_signals(
            signal_df, price_df,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        return MultiAgentBacktestResult(
            mode="multi_agent",
            eval_summary=summary,
            total_dates=(end_date - start_date).days + 1,
            total_signals=summary.total_signals,
            details=merged,
        )

    def _get_date_sentiment(
        self,
        hist_df: pd.DataFrame,
        trade_date: date,
        symbols: Sequence[str],
    ) -> Optional[tuple[List[OpinionSnapshot], Dict[date, Dict[str, AggregatedSentiment]]]]:
        """Extract sentiment data for a single date from historical signals."""
        if hist_df.empty:
            return None

        day_df = hist_df[
            hist_df["trade_date"] == pd.Timestamp(trade_date)
        ]
        if day_df.empty:
            return None

        snapshots: List[OpinionSnapshot] = []
        aggregated: Dict[date, Dict[str, AggregatedSentiment]] = {}
        date_inner: Dict[str, AggregatedSentiment] = {}

        for _, row in day_df.iterrows():
            sym = str(row.get("symbol", ""))
            if not sym:
                continue
            score = float(row.get("score", row.get("consensus_score", 0.0)))
            float(row.get("confidence", 0.0))

            snapshots.append(
                OpinionSnapshot(
                    timestamp=datetime.combine(trade_date, datetime.min.time()),
                    trade_date=trade_date,
                    platform="guba",
                    symbol=sym,
                    sentiment_score=score,
                    post_count=1,
                    source="backtest_history",
                )
            )
            date_inner[sym] = AggregatedSentiment(
                trade_date=trade_date,
                symbol=sym,
                platform_scores={"guba": score},
                platform_weights=self.config.strategy.platform_weights,
            )

        aggregated[trade_date] = date_inner
        return snapshots, aggregated


def comparison_to_dataframe(cmp: BacktestComparison) -> pd.DataFrame:
    """Format a BacktestComparison into a human-readable summary DataFrame."""
    rows = [
        {
            "Metric": "Accuracy",
            "Sentiment Only": f"{cmp.sentiment.eval_summary.accuracy:.2%}",
            "Multi-Agent": f"{cmp.multi_agent.eval_summary.accuracy:.2%}",
        },
        {
            "Metric": "Avg Return",
            "Sentiment Only": f"{cmp.sentiment.eval_summary.avg_return:.4%}",
            "Multi-Agent": f"{cmp.multi_agent.eval_summary.avg_return:.4%}",
        },
        {
            "Metric": "Win Rate",
            "Sentiment Only": f"{cmp.sentiment.eval_summary.win_rate:.2%}",
            "Multi-Agent": f"{cmp.multi_agent.eval_summary.win_rate:.2%}",
        },
        {
            "Metric": "Sharpe-like",
            "Sentiment Only": f"{cmp.sentiment.eval_summary.sharpe_like:.4f}",
            "Multi-Agent": f"{cmp.multi_agent.eval_summary.sharpe_like:.4f}",
        },
        {
            "Metric": "Total Signals",
            "Sentiment Only": str(cmp.sentiment.total_signals),
            "Multi-Agent": str(cmp.multi_agent.total_signals),
        },
    ]
    return pd.DataFrame(rows)
