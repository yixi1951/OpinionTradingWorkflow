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
) -> pd.DataFrame:
    """Return DataFrame: trade_date, cash, position_value, total_value, drawdown_pct."""
    from opinion_trading.skills.trade_simulation import PaperTradingSkill

    trades = _load_trades(memory_dir)
    skill = PaperTradingSkill(
        initial_cash, 0.2, use_market_prices=use_market_prices and price_df is None
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

    price_lookup: Dict[tuple, float] = {}
    if price_df is not None and not price_df.empty:
        view = price_df.copy()
        view["date"] = pd.to_datetime(view["date"], errors="coerce").dt.date
        for _, row in view.dropna(subset=["date", "symbol"]).iterrows():
            try:
                price_lookup[(row["date"], str(row["symbol"]))] = float(row["close"])
            except (TypeError, ValueError):
                continue

    for td in sorted(by_date.keys()):
        for tr in by_date[td]:
            if tr.action == "BUY":
                positions[tr.symbol] = positions.get(tr.symbol, 0) + tr.shares
            elif tr.action == "SELL":
                positions[tr.symbol] = max(0, positions.get(tr.symbol, 0) - tr.shares)
            cash = tr.cash_after

        if price_lookup:
            pos_val = 0.0
            for sym, shares in positions.items():
                if shares <= 0:
                    continue
                mark = price_lookup.get((td, sym))
                if mark is None:
                    # fall back to last trade price for the symbol that day
                    day_trades = [t for t in by_date[td] if t.symbol == sym]
                    mark = float(day_trades[-1].price) if day_trades else 0.0
                pos_val += shares * float(mark)
            total = cash + pos_val
        else:
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


def align_paper_vs_eval(
    memory_dir: str,
    price_df: pd.DataFrame,
    signal_path: str,
    *,
    report_dir: str,
    initial_cash: float = 100_000.0,
) -> Dict[str, Any]:
    """Compare paper equity curve against evaluate_signals summary and write a report."""
    from dataclasses import asdict, is_dataclass

    from opinion_trading.core.evaluation import evaluate_signals, load_prices
    from opinion_trading.core.monthly_training import load_training_history

    paper = build_paper_equity_curve(
        memory_dir, initial_cash=initial_cash, price_df=price_df, use_market_prices=False
    )
    signals = load_training_history(memory_dir)
    if Path(signal_path).is_file() and (
        signals is None or getattr(signals, "empty", True)
    ):
        signals = pd.read_json(signal_path, lines=True)
    if signals is None:
        signals = pd.DataFrame()
    if not signals.empty and "trade_date" in signals.columns:
        signals = signals.copy()
        signals["trade_date"] = pd.to_datetime(signals["trade_date"], errors="coerce")

    prices = price_df
    try:
        if prices is None or prices.empty:
            prices = load_prices(str(Path(report_dir) / "price_history_template.csv"))
    except Exception:
        prices = price_df

    eval_signals = 0
    eval_summary: Dict[str, Any] = {}
    try:
        _merged, summary = evaluate_signals(signals, prices)
        eval_signals = int(getattr(summary, "total_signals", len(_merged) if _merged is not None else 0))
        if is_dataclass(summary):
            eval_summary = asdict(summary)
        elif hasattr(summary, "__dict__"):
            eval_summary = dict(summary.__dict__)
        else:
            eval_summary = {"total_signals": eval_signals}
    except Exception as exc:
        # Still count raw signal rows so alignment report is useful without perfect prices.
        eval_signals = int(len(signals)) if signals is not None else 0
        eval_summary = {"error": str(exc)[:200], "raw_signals": eval_signals}

    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "paper_vs_eval.md"
    json_path = out_dir / "paper_vs_eval.json"
    payload = {
        "paper_days": int(len(paper)),
        "eval_signals": eval_signals,
        "paper_final_value": float(paper.iloc[-1]["total_value"]) if len(paper) else None,
        "eval_summary": eval_summary,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        "# Paper vs Eval Alignment\n\n"
        f"- paper_days: {payload['paper_days']}\n"
        f"- eval_signals: {payload['eval_signals']}\n"
        f"- paper_final_value: {payload['paper_final_value']}\n",
        encoding="utf-8",
    )
    payload["paths"] = {"md": str(md_path), "json": str(json_path)}
    return payload


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
