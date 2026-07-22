"""Technical analyst: scores stocks based on price indicators.

Fetches OHLCV data, computes RSI / MACD / Bollinger Bands / ATR / volume,
and produces a score (-1 to +1) from the multi-timeframe trend + momentum.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict

import pandas as pd

from opinion_trading.agents.analyst_base import AnalystOpinion, BaseAnalyst
from opinion_trading.core.log_utils import get_logger
from opinion_trading.core.market_data import fetch_ohlcv
from opinion_trading.core.technical_indicators import analyst_score, compute_all_indicators

logger = get_logger(__name__)


class TechnicalAnalyst(BaseAnalyst):
    """Technical analysis agent using price/volume indicators."""

    def __init__(
        self,
        lookback_days: int = 365,
        min_history_days: int = 20,
    ) -> None:
        self.lookback_days = lookback_days
        self.min_history_days = min_history_days

    @property
    def name(self) -> str:
        return "technical"

    def analyze(self, symbol: str, trade_date: date) -> AnalystOpinion | None:
        end = trade_date
        start = end - timedelta(days=self.lookback_days)

        df = fetch_ohlcv(symbol, start_date=start.isoformat(), end_date=end.isoformat())
        if df.empty or len(df) < self.min_history_days:
            logger.debug("TechnicalAnalyst: insufficient data for %s (%d rows)", symbol, len(df))
            return None

        # Filter to rows <= trade_date
        df = df[df.index <= pd.Timestamp(end)]
        if len(df) < self.min_history_days:
            return None

        df_ind = compute_all_indicators(df)
        scores = analyst_score(df_ind)

        overall = scores["score"]
        confidence = self._compute_confidence(df_ind, scores)

        reasoning = self._build_reasoning(symbol, scores, df_ind)
        sub_scores = {k: v for k, v in scores.items() if k != "score"}

        return AnalystOpinion(
            symbol=symbol,
            trade_date=trade_date,
            analyst_name=self.name,
            score=overall,
            confidence=confidence,
            reasoning=reasoning,
            sub_scores=sub_scores,
            metadata={
                "data_rows": len(df),
                "latest_close": float(df["Close"].iloc[-1]) if "Close" in df else 0,
            },
        )

    def _compute_confidence(self, df: pd.DataFrame, scores: Dict[str, float]) -> float:
        """Confidence based on data quality and signal coherence."""
        base = 0.5
        # More history = more confident
        if len(df) > 200:
            base += 0.2
        elif len(df) > 60:
            base += 0.1

        # Strong directional signals boost confidence
        abs_score = abs(scores.get("score", 0))
        if abs_score > 0.5:
            base += 0.15
        elif abs_score > 0.3:
            base += 0.05

        return min(0.95, base)

    def _build_reasoning(
        self, symbol: str, scores: Dict[str, float], df: pd.DataFrame
    ) -> str:
        parts = [f"{symbol} 技术分析:"]

        trend = scores.get("trend", 0)
        if trend > 0.3:
            parts.append(f"趋势偏多 ({trend:+.2f})")
        elif trend < -0.3:
            parts.append(f"趋势偏空 ({trend:+.2f})")
        else:
            parts.append(f"趋势中性 ({trend:+.2f})")

        mom = scores.get("momentum", 0)
        if mom > 0.3:
            parts.append(f"动量向上 ({mom:+.2f})")
        elif mom < -0.3:
            parts.append(f"动量向下 ({mom:+.2f})")
        else:
            parts.append(f"动量中性 ({mom:+.2f})")

        vol = scores.get("volatility_risk", 0)
        if abs(vol) > 0.3:
            parts.append(f"波动率风险{'高' if vol < -0.3 else '低'} ({vol:+.2f})")

        vol_health = scores.get("volume_health", 0)
        if vol_health > 0.2:
            parts.append("成交量健康")
        elif vol_health < -0.3:
            parts.append("成交量萎缩")

        # Add latest indicator values
        if "RSI" in df.columns and not df["RSI"].dropna().empty:
            rsi = float(df["RSI"].iloc[-1])
            parts.append(f"RSI {rsi:.0f}")
        if "MACD_Hist" in df.columns and not df["MACD_Hist"].dropna().empty:
            mh = float(df["MACD_Hist"].iloc[-1])
            parts.append(f"MACD柱 {mh:+.3f}")

        return " | ".join(parts)
