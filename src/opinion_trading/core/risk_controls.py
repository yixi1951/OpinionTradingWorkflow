"""Unified risk layer (paper / dry-run; hooks for future live trading)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import os
from typing import Dict, List, Optional, Tuple

from opinion_trading.core.models import TradeSignal


@dataclass
class RiskLimits:
    max_daily_loss_pct: float = 0.05
    max_single_symbol_notional_pct: float = 0.25
    max_open_positions: int = 10
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    max_concurrent_orders: int = 3


@dataclass
class RiskCheckResult:
    allowed: List[TradeSignal] = field(default_factory=list)
    rejected: List[Tuple[TradeSignal, str]] = field(default_factory=list)
    trading_halted: bool = False
    halt_reason: str = ""


def is_trading_halted(state: Optional[Dict] = None) -> Tuple[bool, str]:
    if os.environ.get("KILL_SWITCH", "0") == "1":
        return True, "kill_switch"
    state = state or {}
    if state.get("trading_halted"):
        return True, str(state.get("halt_reason") or "state_halted")
    return False, ""


def set_kill_switch(
    state: Optional[Dict] = None, enabled: bool = True, *, reason: str = "kill_switch"
) -> Dict:
    """Persist a trading halt flag into portfolio/workflow state (and optionally env)."""
    out = dict(state or {})
    if enabled:
        out["trading_halted"] = True
        out["halt_reason"] = reason or "kill_switch"
        os.environ["KILL_SWITCH"] = "1"
    else:
        out["trading_halted"] = False
        out["halt_reason"] = ""
        os.environ["KILL_SWITCH"] = "0"
    return out


def clear_trading_halt(state: Optional[Dict] = None) -> Dict:
    out = dict(state or {})
    out["trading_halted"] = False
    out["halt_reason"] = ""
    if os.environ.get("KILL_SWITCH") == "1":
        # clear_trading_halt only clears state halt; leave env kill switch alone
        # unless it was set by set_kill_switch during a drill — callers may reset env.
        pass
    return out


def generate_exit_signals(positions, entry_prices, current_prices, *, trade_date: date, limits: RiskLimits):
    exits = []
    for symbol, shares in positions.items():
        if int(shares or 0) <= 0 or float(entry_prices.get(symbol, 0) or 0) <= 0:
            continue
        entry = float(entry_prices[symbol])
        current = float(current_prices.get(symbol, 0) or 0)
        if current <= 0:
            continue
        change = current / entry - 1
        reason = ""
        if limits.stop_loss_pct and change <= -abs(limits.stop_loss_pct):
            reason = f"stop_loss {change:.2%}"
        elif limits.take_profit_pct and change >= abs(limits.take_profit_pct):
            reason = f"take_profit {change:.2%}"
        if reason:
            exits.append(TradeSignal(trade_date=trade_date, symbol=symbol, action="SELL", confidence=1.0, reason=reason, platforms=[]))
    return exits


def apply_risk_to_signals(
    signals: List[TradeSignal],
    *,
    portfolio_value: float,
    cash: float,
    positions: Dict[str, int],
    limits: RiskLimits,
    reference_prices: Optional[Dict[str, float]] = None,
    pending_order_count: int = 0,
    day_start_equity: Optional[float] = None,
    trading_already_halted: bool = False,
    halt_reason: str = "",
) -> RiskCheckResult:
    """Filter signals before paper/live execution."""
    if portfolio_value <= 0:
        portfolio_value = max(cash, 1.0)

    open_count = sum(1 for sh in positions.values() if sh > 0)
    result = RiskCheckResult()
    env_halted, env_reason = is_trading_halted({})
    if trading_already_halted or env_halted:
        result.trading_halted = True
        result.halt_reason = halt_reason or env_reason
        result.rejected = [(sig, result.halt_reason) for sig in signals]
        return result
    if day_start_equity and day_start_equity > 0 and portfolio_value < day_start_equity * (1 - limits.max_daily_loss_pct):
        result.trading_halted = True
        result.halt_reason = "max_daily_loss"
        result.rejected = [(sig, result.halt_reason) for sig in signals]
        return result

    accepted_orders = 0

    for sig in signals:
        if sig.action == "BUY":
            if pending_order_count + accepted_orders >= limits.max_concurrent_orders:
                result.rejected.append((sig, "max_concurrent_orders"))
                continue
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
        if sig.action in ("BUY", "SELL"):
            accepted_orders += 1

    return result
