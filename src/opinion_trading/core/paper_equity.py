"""Paper portfolio equity curve from trade_history.jsonl (P1: align with paper account)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from opinion_trading.core.models import PaperTrade


def _load_trades(memory_dir: str) -> List[PaperTrade]:
    path = Path(memory_dir) / "trade_history.jsonl"
    if not path.is_file():
        return []
    out: List[PaperTrade] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            out.append(
                PaperTrade(
                    trade_date=date.fromisoformat(str(row["trade_date"])[:10]),
                    symbol=str(row["symbol"]),
                    action=str(row["action"]),
                    shares=int(row["shares"]),
                    price=float(row["price"]),
                    cash_after=float(row["cash_after"]),
                    note=str(row.get("note", "")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda t: (t.trade_date, t.symbol, t.action))
    return out


def build_paper_equity_curve(
    memory_dir: str,
    *,
    initial_cash: float = 100_000.0,
    use_market_prices: bool = True,
) -> pd.DataFrame:
    """Return DataFrame: trade_date, cash, position_value, total_value, drawdown_pct."""
    from opinion_trading.skills.trade_simulation import PaperTradingSkill

    trades = _load_trades(memory_dir)
    skill = PaperTradingSkill(
        initial_cash, 0.2, use_market_prices=use_market_prices
    )

    if not trades:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "cash",
                "position_value",
                "total_value",
                "drawdown_pct",
            ]
        )

    cash = float(initial_cash)
    positions: Dict[str, int] = {}
    rows: List[Dict[str, Any]] = []

    by_date: Dict[date, List[PaperTrade]] = {}
    for tr in trades:
        by_date.setdefault(tr.trade_date, []).append(tr)

    for td in sorted(by_date.keys()):
        for tr in by_date[td]:
            if tr.action == "BUY":
                positions[tr.symbol] = positions.get(tr.symbol, 0) + tr.shares
            elif tr.action == "SELL":
                positions[tr.symbol] = max(0, positions.get(tr.symbol, 0) - tr.shares)
            cash = tr.cash_after

        state = {
            "cash": cash,
            "positions": dict(positions),
            "last_run_date": td.isoformat(),
        }
        total = skill.portfolio_value({}, state)
        pos_val = max(0.0, total - cash)
        rows.append(
            {
                "trade_date": td,
                "cash": cash,
                "position_value": round(pos_val, 2),
                "total_value": round(total, 2),
            }
        )

    df = pd.DataFrame(rows)
    peak = df["total_value"].cummax()
    df["drawdown_pct"] = ((df["total_value"] - peak) / peak.replace(0, 1e-12)).fillna(
        0
    )
    return df


def discover_raw_trade_dates(raw_dir: str) -> List[str]:
    """ISO dates from raw_posts_YYYY-MM-DD.csv filenames."""
    root = Path(raw_dir)
    if not root.is_dir():
        return []
    dates: List[str] = []
    for p in sorted(root.glob("raw_posts_*.csv")):
        stem = p.stem.replace("raw_posts_", "")
        if len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
            dates.append(stem)
    return sorted(set(dates))
