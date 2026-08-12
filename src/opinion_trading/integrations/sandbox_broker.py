"""Local sandbox broker — JSON ledger, fills, and position reconcile (no live API)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from opinion_trading.core.audit_log import AuditLogger, new_trace_id
from opinion_trading.core.http_retry import make_idempotency_key
from opinion_trading.core.idempotency import IdempotencyStore
from opinion_trading.integrations.broker_adapter import BaseBrokerAdapter, ExecutionIntent


class SandboxBrokerAdapter(BaseBrokerAdapter):
    """In-process sandbox with cash/positions ledger under memory_dir."""

    def __init__(
        self,
        report_dir: str = "data/reports",
        *,
        memory_dir: str = "data/memory",
        initial_cash: float = 100_000.0,
        slippage_bps: float = 5.0,
        idempotency: Optional[IdempotencyStore] = None,
        audit: Optional[AuditLogger] = None,
    ) -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.memory_dir / "sandbox_ledger.json"
        self.initial_cash = float(initial_cash)
        self.slippage_bps = float(slippage_bps)
        self.idempotency = idempotency or IdempotencyStore(
            str(self.memory_dir / "idempotency")
        )
        self.audit = audit or AuditLogger(
            str(self.memory_dir / "audit_trail.jsonl")
        )
        self._ensure_ledger()

    def _ensure_ledger(self) -> Dict:
        if not self.ledger_path.is_file():
            ledger = {
                "cash": self.initial_cash,
                "positions": {},
                "avg_cost": {},
                "orders": [],
            }
            self._save_ledger(ledger)
            return ledger
        return self._load_ledger()

    def _load_ledger(self) -> Dict:
        try:
            return json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "cash": self.initial_cash,
                "positions": {},
                "avg_cost": {},
                "orders": [],
            }

    def _save_ledger(self, ledger: Dict) -> None:
        self.ledger_path.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def fetch_positions(self) -> Dict[str, int]:
        ledger = self._load_ledger()
        return {
            str(k): int(v)
            for k, v in dict(ledger.get("positions") or {}).items()
            if int(v or 0) != 0
        }

    def fetch_ledger(self) -> Dict:
        return self._load_ledger()

    def submit_intents(
        self,
        intents: List[ExecutionIntent],
        *,
        prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, object]:
        if not intents:
            return {"path": "", "count": 0, "skipped_duplicate": 0, "fills": []}

        prices = prices or {}
        day = intents[0].trade_date
        path = self.report_dir / f"sandbox_fills_{day}.jsonl"
        ledger = self._load_ledger()
        cash = float(ledger.get("cash", self.initial_cash))
        positions: Dict[str, int] = {
            str(k): int(v) for k, v in dict(ledger.get("positions") or {}).items()
        }
        avg_cost: Dict[str, float] = {
            str(k): float(v) for k, v in dict(ledger.get("avg_cost") or {}).items()
        }
        orders: List[Dict] = list(ledger.get("orders") or [])
        slip = self.slippage_bps / 10_000.0
        written = 0
        skipped = 0
        fills: List[Dict] = []

        with path.open("a", encoding="utf-8") as f:
            for intent in intents:
                rid = intent.request_id or make_idempotency_key(
                    intent.trade_date,
                    intent.symbol,
                    intent.side,
                    intent.reason[:80],
                    prefix="ord",
                )
                intent.request_id = rid
                if not intent.trace_id:
                    intent.trace_id = new_trace_id()
                if not intent.order_id:
                    intent.order_id = rid

                if not self.idempotency.remember(
                    "orders",
                    rid,
                    payload={"symbol": intent.symbol, "side": intent.side},
                ):
                    skipped += 1
                    self.audit.emit(
                        "order_duplicate_skipped",
                        trace_id=intent.trace_id,
                        order_id=intent.order_id,
                        request_id=rid,
                        symbol=intent.symbol,
                    )
                    continue

                px = float(prices.get(intent.symbol) or 0.0)
                if px <= 0:
                    row = {
                        "status": "rejected",
                        "reason": "no_price",
                        "intent": intent.to_dict(),
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fills.append(row)
                    written += 1
                    self.audit.emit(
                        "order_rejected",
                        request_id=rid,
                        symbol=intent.symbol,
                        reason="no_price",
                    )
                    continue

                fill_px = px * (1 + slip) if intent.side == "BUY" else px * (1 - slip)
                ratio = max(0.0, min(1.0, float(intent.suggested_notional_ratio)))
                equity_proxy = cash + sum(
                    sh * float(prices.get(sym) or avg_cost.get(sym) or fill_px)
                    for sym, sh in positions.items()
                    if sh > 0
                )
                notional = equity_proxy * ratio
                shares = int(notional // fill_px) if fill_px > 0 else 0

                status = "filled"
                reason = ""
                if intent.side == "BUY":
                    if shares <= 0:
                        status = "rejected"
                        reason = "zero_shares"
                    elif shares * fill_px > cash + 1e-9:
                        shares = int(cash // fill_px)
                        if shares <= 0:
                            status = "rejected"
                            reason = "insufficient_cash"
                    if status == "filled":
                        cost_old = avg_cost.get(intent.symbol, 0.0)
                        pos_old = positions.get(intent.symbol, 0)
                        new_pos = pos_old + shares
                        if new_pos > 0:
                            avg_cost[intent.symbol] = (
                                (cost_old * pos_old + fill_px * shares) / new_pos
                            )
                        positions[intent.symbol] = new_pos
                        cash -= shares * fill_px
                else:  # SELL
                    held = positions.get(intent.symbol, 0)
                    if held <= 0:
                        status = "rejected"
                        reason = "no_position"
                        shares = 0
                    else:
                        shares = held
                        cash += shares * fill_px
                        positions[intent.symbol] = 0
                        avg_cost.pop(intent.symbol, None)

                row = {
                    "status": status,
                    "reason": reason,
                    "symbol": intent.symbol,
                    "side": intent.side,
                    "shares": shares,
                    "price": round(fill_px, 4),
                    "reference_price": round(px, 4),
                    "slippage_bps": self.slippage_bps,
                    "request_id": rid,
                    "trace_id": intent.trace_id,
                    "filled_at": datetime.now().isoformat(),
                    "dry_run": intent.dry_run,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                fills.append(row)
                written += 1
                orders.append(row)
                self.audit.emit(
                    "order_submitted" if status == "filled" else "order_rejected",
                    trace_id=intent.trace_id,
                    order_id=intent.order_id,
                    request_id=rid,
                    symbol=intent.symbol,
                    side=intent.side,
                    dry_run=intent.dry_run,
                    status=status,
                    reason=reason or intent.reason[:200],
                )

        ledger = {
            "cash": round(cash, 2),
            "positions": {k: v for k, v in positions.items() if v != 0},
            "avg_cost": avg_cost,
            "orders": orders[-500:],
            "updated_at": datetime.now().isoformat(),
        }
        self._save_ledger(ledger)
        return {
            "path": str(path),
            "count": written,
            "skipped_duplicate": skipped,
            "fills": fills,
            "dry_run": True,
            "ledger_cash": ledger["cash"],
            "ledger_positions": dict(ledger["positions"]),
        }

    def reconcile(
        self, expected_state: Dict
    ) -> Tuple[bool, List[Dict[str, object]]]:
        """Compare workflow paper state vs sandbox ledger; return (ok, mismatches)."""
        ledger = self._load_ledger()
        mismatches: List[Dict[str, object]] = []

        exp_pos = {
            str(k): int(v)
            for k, v in dict(expected_state.get("positions") or {}).items()
            if int(v or 0) != 0
        }
        led_pos = {
            str(k): int(v)
            for k, v in dict(ledger.get("positions") or {}).items()
            if int(v or 0) != 0
        }
        all_syms = sorted(set(exp_pos) | set(led_pos))
        for sym in all_syms:
            a, b = exp_pos.get(sym, 0), led_pos.get(sym, 0)
            if a != b:
                mismatches.append(
                    {
                        "field": "position",
                        "symbol": sym,
                        "expected": a,
                        "ledger": b,
                    }
                )

        if mismatches:
            for m in mismatches:
                self.audit.emit(
                    "recon_mismatch",
                    symbol=str(m.get("symbol", "")),
                    expected=m.get("expected"),
                    ledger=m.get("ledger"),
                    field=m.get("field"),
                )
        else:
            self.audit.emit("recon_ok", positions=len(led_pos))

        return len(mismatches) == 0, mismatches
