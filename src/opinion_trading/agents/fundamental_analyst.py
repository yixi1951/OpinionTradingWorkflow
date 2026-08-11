"""Fundamental analyst: scores stocks based on fundamentals.

Fetches PE, PB, ROE, revenue growth, beta, margins, and market cap
via yfinance (with akshare fallback for A-shares).
"""

from __future__ import annotations

from datetime import date

from opinion_trading.agents.analyst_base import AnalystOpinion, BaseAnalyst
from opinion_trading.core.fundamentals import analyst_score as compute_fund_score
from opinion_trading.core.fundamentals import fetch_fundamentals
from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)


class FundamentalAnalyst(BaseAnalyst):
    """Fundamental analysis agent using financial metrics."""

    @property
    def name(self) -> str:
        return "fundamental"

    def analyze(self, symbol: str, trade_date: date) -> AnalystOpinion | None:
        fundamentals = fetch_fundamentals(symbol)
        if not fundamentals:
            logger.debug("FundamentalAnalyst: no data for %s", symbol)
            return None

        scores = compute_fund_score(fundamentals)
        overall = scores.get("score", 0.0)

        confidence = self._compute_confidence(fundamentals, scores)
        reasoning = self._build_reasoning(symbol, fundamentals, scores)

        sub_scores = {k: v for k, v in scores.items() if k != "score"}

        # Build metadata
        meta = {}
        for k in ("pe", "pb", "roe", "market_cap", "revenue_growth",
                   "sector", "industry", "beta", "dividend_yield"):
            v = fundamentals.get(k)
            if v is not None:
                meta[k] = v

        return AnalystOpinion(
            symbol=symbol,
            trade_date=trade_date,
            analyst_name=self.name,
            score=overall,
            confidence=confidence,
            reasoning=reasoning,
            sub_scores=sub_scores,
            metadata=meta,
        )

    def _compute_confidence(self, fund: dict, scores: dict) -> float:
        """Confidence based on data completeness."""
        data_points = sum(
            1 for k in ("pe", "roe", "revenue_growth", "market_cap", "beta")
            if fund.get(k) is not None
        )
        base = 0.3 + data_points * 0.1
        if abs(scores.get("score", 0)) > 0.4:
            base += 0.1
        return min(0.9, base)

    def _build_reasoning(self, symbol: str, fund: dict, scores: dict) -> str:
        parts = [f"{symbol} 基本面分析:"]

        pe = fund.get("pe")
        if pe is not None:
            parts.append(f"PE {pe:.1f}")
        roe = fund.get("roe")
        if roe is not None:
            parts.append(f"ROE {float(roe)*100:.1f}%")
        growth = fund.get("revenue_growth")
        if growth is not None:
            parts.append(f"营收增长 {float(growth)*100:.1f}%")
        sector = fund.get("sector") or fund.get("industry", "")
        if sector:
            parts.append(f"行业: {sector}")

        overall = scores.get("score", 0)
        if overall > 0.3:
            parts.append("估值偏低/质量好 → 看多")
        elif overall < -0.3:
            parts.append("估值偏高/质量差 → 看空")
        else:
            parts.append("估值中性")

        return " | ".join(parts)
