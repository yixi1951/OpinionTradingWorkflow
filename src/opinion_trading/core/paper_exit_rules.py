"""Paper-only take-profit / stop-loss scaffold (research; no live orders)."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

from opinion_trading.core.evaluation import apply_fill_price, lookup_close
from opinion_trading.core.models import PaperExitConfig, PaperTrade, TradeSignal
from opinion_trading.core.transaction_costs import TransactionCostConfig


def load_paper_exit_config(raw: Optional[dict] = None) -> PaperExitConfig:
    import os

    exec_raw = (raw or {}).get("execution", {}) or {}
    block = exec_raw.get("paper_exit", {}) or {}
    env_on = os.environ.get("PAPER_EXIT_RULES", "").strip().lower()
    enabled = bool(block.get("enabled", False))
    if env_on in ("1", "true", "yes", "on"):
        enabled = True
    elif env_on in ("0", "false", "no", "off"):
        enabled = False
    return PaperExitConfig(
        enabled=enabled,
        take_profit_pct=float(block.get("take_profit_pct", 0.10)),
        stop_loss_pct=float(block.get("stop_loss_pct", 0.05)),
    )


def _entry_price_for_symbol(
    memory_dir: str, symbol: str, fallback: float
) -> float:
    from pathlib import Path
    import json

    path = Path(memory_dir) / "position_entries.json"
    if not path.exists():
        return fallback
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entry = data.get(symbol)
        if entry and float(entry.get("price", 0)) > 0:
            return float(entry["price"])
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return fallback


def record_entry_prices(
    memory_dir: str,
    trades: List[PaperTrade],
    state_positions: Dict[str, int],
) -> None:
    """Track average entry for open lots (paper research scaffold)."""
    from pathlib import Path
    import json

    path = Path(memory_dir) / "position_entries.json"
    data: Dict[str, Dict] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    for tr in trades:
        if tr.action != "BUY":
            continue
        sym = tr.symbol
        prev = data.get(sym, {"shares": 0, "cost": 0.0})
        sh = int(prev.get("shares", 0)) + tr.shares
        cost = float(prev.get("cost", 0.0)) + tr.shares * tr.price
        if sh > 0:
            data[sym] = {"shares": sh, "cost": cost, "price": cost / sh}
    for sym, shares in state_positions.items():
        if int(shares) <= 0 and sym in data:
            del data[sym]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def evaluate_paper_exits(
    trade_date: date,
    state: Dict,
    *,
    price_df,
    config: PaperExitConfig,
    memory_dir: str,
    slippage_bps: float = 0.0,
    fee_bps: float = 0.0,
    transaction_costs: TransactionCostConfig | None = None,
) -> Tuple[List[TradeSignal], List[Dict]]:
    """Return SELL signals and diagnostic rows for TP/SL hits."""
    if not config.enabled or price_df is None:
        return [], []
    positions: Dict[str, int] = {
        k: int(v) for k, v in dict(state.get("positions", {})).items() if int(v) > 0
    }
    if not positions:
        return [], []
    signals: List[TradeSignal] = []
    diagnostics: List[Dict] = []
    for symbol, shares in positions.items():
        mtm = lookup_close(price_df, symbol, trade_date)
        if mtm is None or mtm <= 0:
            continue
        entry = _entry_price_for_symbol(memory_dir, symbol, float(mtm))
        if entry <= 0:
            continue
        pnl_pct = (float(mtm) - entry) / entry
        reason = ""
        if pnl_pct >= config.take_profit_pct:
            reason = f"paper_take_profit {pnl_pct:.2%} >= {config.take_profit_pct:.2%}"
        elif pnl_pct <= -config.stop_loss_pct:
            reason = f"paper_stop_loss {pnl_pct:.2%} <= -{config.stop_loss_pct:.2%}"
        else:
            continue
        fill_px = apply_fill_price(
            float(mtm),
            "SELL",
            slippage_bps=slippage_bps,
            fee_bps=fee_bps,
            trade_date=trade_date,
            transaction_costs=transaction_costs,
        )
        diagnostics.append(
            {
                "symbol": symbol,
                "shares": shares,
                "entry_price": entry,
                "mtm_price": float(mtm),
                "pnl_pct": round(pnl_pct, 6),
                "fill_price": round(fill_px, 4),
                "reason": reason,
            }
        )
        signals.append(
            TradeSignal(
                trade_date=trade_date,
                symbol=symbol,
                action="SELL",
                confidence=1.0,
                reason=reason,
                platforms=["paper_exit"],
                consensus_score=None,
                explanation=reason,
            )
        )
    return signals, diagnostics
