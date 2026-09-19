"""Unified risk layer (paper / dry-run; hooks for future live trading)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from opinion_trading.core.models import TradeSignal


@dataclass
class RiskLimits:
    max_daily_loss_pct: float = 0.05
    max_single_symbol_notional_pct: float = 0.25
    max_open_positions: int = 10


@dataclass
class RiskCheckResult:
    allowed: List[TradeSignal] = field(default_factory=list)
    rejected: List[Tuple[TradeSignal, str]] = field(default_factory=list)


def apply_risk_to_signals(
    signals: List[TradeSignal],
    *,
    portfolio_value: float,
    cash: float,
    positions: Dict[str, int],
    limits: RiskLimits,
    reference_prices: Optional[Dict[str, float]] = None,
) -> RiskCheckResult:
    """Filter signals before paper/live execution."""
    if portfolio_value <= 0:
        portfolio_value = max(cash, 1.0)

    open_count = sum(1 for sh in positions.values() if sh > 0)
    result = RiskCheckResult()

    for sig in signals:
        if sig.action == "BUY":
            if open_count >= limits.max_open_positions and positions.get(sig.symbol, 0) <= 0:
                result.rejected.append((sig, "max_open_positions"))
                continue
            ratio = sig.kelly_fraction if sig.kelly_fraction is not None else 0.2
            if ratio > limits.max_single_symbol_notional_pct:
                result.rejected.append(
                    (sig, f"single_symbol_notional>{limits.max_single_symbol_notional_pct:.0%}")
                )
                continue
        result.allowed.append(sig)

    return result
