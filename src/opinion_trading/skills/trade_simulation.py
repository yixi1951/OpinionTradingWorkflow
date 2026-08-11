from __future__ import annotations

import random
from datetime import date
from typing import Dict, List, Tuple

from opinion_trading.core.log_utils import get_logger
from opinion_trading.core.market_data import fetch_closes_for_symbols
from opinion_trading.core.models import AggregatedSentiment, PaperTrade, TradeSignal

logger = get_logger(__name__)


class PaperTradingSkill:
    def __init__(
        self,
        initial_cash: float,
        position_size_ratio: float,
        *,
        use_market_prices: bool = True,
    ) -> None:
        self.initial_cash = initial_cash
        self.position_size_ratio = position_size_ratio
        self.use_market_prices = use_market_prices

    def simulate(
        self,
        trade_date: date,
        signals: List[TradeSignal],
        today_aggregated: Dict[str, AggregatedSentiment],
        state: Dict,
    ) -> Tuple[List[PaperTrade], Dict]:
        cash = float(state.get("cash", self.initial_cash))
        positions: Dict[str, int] = dict(state.get("positions", {}))

        symbols_needed = sorted(
            set(
                [s.symbol for s in signals]
                + [sym for sym, sh in positions.items() if sh > 0]
            )
        )
        market_prices: Dict[str, tuple[float | None, str]] = {}
        if self.use_market_prices and symbols_needed:
            market_prices = fetch_closes_for_symbols(symbols_needed, trade_date)

        trades: List[PaperTrade] = []
        for signal in signals:
            price, src = self._resolve_price(
                signal.symbol, trade_date, today_aggregated, market_prices
            )
            if signal.action == "BUY":
                budget = cash * self._size_ratio(signal)
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
                        note=self._trade_note(signal, price, src),
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
                        note=self._trade_note(signal, price, src),
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
        trade_date = date.today()
        if state.get("last_run_date"):
            try:
                trade_date = date.fromisoformat(str(state["last_run_date"]))
            except ValueError:
                pass

        symbols = [sym for sym, sh in positions.items() if sh > 0]
        market_prices: Dict[str, tuple[float | None, str]] = {}
        if self.use_market_prices and symbols:
            market_prices = fetch_closes_for_symbols(symbols, trade_date)

        position_value = 0.0
        for symbol, shares in positions.items():
            if shares <= 0:
                continue
            price, _ = self._resolve_price(
                symbol, trade_date, today_aggregated, market_prices
            )
            position_value += shares * price

        return cash + position_value

    def _size_ratio(self, signal: TradeSignal) -> float:
        if signal.kelly_fraction is not None and signal.kelly_fraction > 0:
            return min(1.0, float(signal.kelly_fraction))
        return self.position_size_ratio

    def _trade_note(self, signal: TradeSignal, price: float, source: str) -> str:
        head = f"[price={price:.2f} src={source}]"
        body = (signal.explanation or signal.reason or "")[:400]
        return f"{head}\n{body}".strip()

    def _resolve_price(
        self,
        symbol: str,
        trade_date: date,
        today_aggregated: Dict[str, AggregatedSentiment],
        market_prices: Dict[str, tuple[float | None, str]],
    ) -> Tuple[float, str]:
        if self.use_market_prices and symbol in market_prices:
            px, src = market_prices[symbol]
            if px is not None and px > 0:
                return float(px), src
            logger.warning(
                "Market price missing for %s on %s, using synthetic fallback",
                symbol,
                trade_date,
            )
        return self._estimate_price(symbol, today_aggregated), "synthetic"

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
