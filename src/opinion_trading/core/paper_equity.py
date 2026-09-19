"""Paper portfolio equity curve from trade_history.jsonl (P1: align with paper account)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    price_df: Optional[pd.DataFrame] = None,
    price_csv: Optional[str] = None,
) -> pd.DataFrame:
    """Return DataFrame: trade_date, cash, position_value, total_value, drawdown_pct.

    When ``price_df`` / ``price_csv`` is provided, marks-to-market use the same
    close table as ``evaluate_signals`` (P1 alignment).
    """
    from opinion_trading.core.evaluation import load_prices
    from opinion_trading.skills.trade_simulation import PaperTradingSkill

    table = price_df
    if table is None and price_csv:
        if Path(price_csv).is_file():
            table = load_prices(price_csv)

    trades = _load_trades(memory_dir)
    skill = PaperTradingSkill(
        initial_cash,
        0.2,
        use_market_prices=use_market_prices,
        price_df=table,
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


def validate_paper_eval_price_alignment(
    price_df: pd.DataFrame,
    memory_dir: str,
    *,
    abs_tol: float = 1e-4,
    rel_tol: float = 1e-6,
) -> Dict[str, Any]:
    """Catch paper MTM vs evaluate_signals close mismatches for overlapping (date, symbol).

    Loads the Eval table into market_data, then compares ``lookup_close`` (evaluate_signals)
    against ``fetch_close_on_date`` (paper equity / paper fills).
    """
    from opinion_trading.core.evaluation import lookup_close
    from opinion_trading.core.market_data import (
        fetch_close_on_date,
        set_local_price_table,
    )

    set_local_price_table(price_df)
    pairs: List[tuple[date, str]] = []
    for tr in _load_trades(memory_dir):
        pairs.append((tr.trade_date, tr.symbol))
    sig_path = Path(memory_dir) / "signal_history.jsonl"
    if sig_path.is_file():
        for line in sig_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                td = date.fromisoformat(str(row["trade_date"])[:10])
                pairs.append((td, str(row["symbol"])))
            except (KeyError, TypeError, ValueError):
                continue

    seen: set[tuple[str, str]] = set()
    mismatches: List[Dict[str, Any]] = []
    compared = 0
    for td, symbol in pairs:
        key = (td.isoformat(), symbol)
        if key in seen:
            continue
        seen.add(key)
        eval_px = lookup_close(price_df, symbol, td)
        if eval_px is None:
            continue
        paper_px, src = fetch_close_on_date(symbol, td)
        compared += 1
        if paper_px is None:
            mismatches.append(
                {
                    "trade_date": td.isoformat(),
                    "symbol": symbol,
                    "eval_close": float(eval_px),
                    "paper_mtm": None,
                    "paper_source": src,
                    "reason": "paper lookup missing",
                }
            )
            continue
        abs_diff = abs(float(paper_px) - float(eval_px))
        rel = abs_diff / max(abs(float(eval_px)), 1e-12)
        if abs_diff > abs_tol and rel > rel_tol:
            mismatches.append(
                {
                    "trade_date": td.isoformat(),
                    "symbol": symbol,
                    "eval_close": float(eval_px),
                    "paper_mtm": float(paper_px),
                    "paper_source": src,
                    "abs_diff": abs_diff,
                }
            )
        elif src not in {"price_table", "market"}:
            # Synthetic/unavailable while Eval has a close is still a mismatch.
            mismatches.append(
                {
                    "trade_date": td.isoformat(),
                    "symbol": symbol,
                    "eval_close": float(eval_px),
                    "paper_mtm": float(paper_px),
                    "paper_source": src,
                    "reason": "paper not using eval price table",
                }
            )
    return {
        "compared": compared,
        "mismatch_count": len(mismatches),
        "aligned": len(mismatches) == 0,
        "mismatches": mismatches,
        "price_source": "price_table",
    }


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
