from __future__ import annotations

import random
from datetime import date
from typing import Dict, List, Tuple

from opinion_trading.core.models import AggregatedSentiment, PaperTrade, TradeSignal


class PaperTradingSkill:
    def __init__(self, initial_cash: float, position_size_ratio: float) -> None:
        self.initial_cash = initial_cash
        self.position_size_ratio = position_size_ratio

    def simulate(
        self,
        trade_date: date,
        signals: List[TradeSignal],
        today_aggregated: Dict[str, AggregatedSentiment],
        state: Dict,
    ) -> Tuple[List[PaperTrade], Dict]:
        cash = float(state.get("cash", self.initial_cash))
        positions: Dict[str, int] = dict(state.get("positions", {}))

        trades: List[PaperTrade] = []
        for signal in signals:
            price = self._estimate_price(signal.symbol, today_aggregated)
            if signal.action == "BUY":
                budget = cash * self.position_size_ratio
                shares = int(budget // price)
                if shares <= 0:
                    continue
                cash -= shares * price
                positions[signal.symbol] = positions.get(signal.symbol, 0) + shares
                trades.append(
                    PaperTrade(
                        trade_date=trade_date,
                        symbol=signal.symbol,
                        action="BUY",
                        shares=shares,
                        price=round(price, 2),
                        cash_after=round(cash, 2),
                        note=signal.reason,
                    )
                )

            if signal.action == "SELL":
                shares = positions.get(signal.symbol, 0)
                if shares <= 0:
                    continue
                cash += shares * price
                positions[signal.symbol] = 0
                trades.append(
                    PaperTrade(
                        trade_date=trade_date,
                        symbol=signal.symbol,
                        action="SELL",
                        shares=shares,
                        price=round(price, 2),
                        cash_after=round(cash, 2),
                        note=signal.reason,
                    )
                )

        updated_state = {
            "cash": round(cash, 2),
            "positions": positions,
            "last_run_date": trade_date.isoformat(),
        }
        return trades, updated_state

    def portfolio_value(
        self, today_aggregated: Dict[str, AggregatedSentiment], state: Dict
    ) -> float:
        cash = float(state.get("cash", self.initial_cash))
        positions: Dict[str, int] = dict(state.get("positions", {}))

        position_value = 0.0
        for symbol, shares in positions.items():
            if shares <= 0:
                continue
            price = self._estimate_price(symbol, today_aggregated)
            position_value += shares * price

        return cash + position_value

    def _estimate_price(
        self, symbol: str, today_aggregated: Dict[str, AggregatedSentiment]
    ) -> float:
        default_price = 20.0
        agg = today_aggregated.get(symbol)
        if agg is None:
            return default_price

        base = 20.0 + (abs(hash(symbol)) % 80)
        sentiment_alpha = 1 + agg.average_score * 0.05
        rng = random.Random(f"{symbol}-{agg.trade_date.isoformat()}")
        noise = rng.uniform(-0.02, 0.02)
        price = base * sentiment_alpha * (1 + noise)
        return max(1.0, price)
