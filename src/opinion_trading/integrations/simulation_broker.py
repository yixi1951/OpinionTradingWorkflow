"""Simulated matching broker — fills at reference price, no exchange API."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from opinion_trading.integrations.broker_adapter import ExecutionIntent


class SimulationBrokerAdapter:
    """Turns execution intents into simulated fills (JSONL audit)."""

    def __init__(self, report_dir: str = "data/reports") -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def match_intents(
        self,
        intents: List[ExecutionIntent],
        *,
        prices: Dict[str, float],
        slippage_bps: float = 5.0,
    ) -> Dict[str, object]:
        if not intents:
            return {"path": "", "count": 0, "fills": []}
        day = intents[0].trade_date
        path = self.report_dir / f"simulated_fills_{day}.jsonl"
        fills: List[Dict] = []
        slip = slippage_bps / 10_000.0
        with path.open("a", encoding="utf-8") as f:
            for intent in intents:
                px = prices.get(intent.symbol)
                if px is None or px <= 0:
                    row = {
                        "status": "rejected",
                        "reason": "no_price",
                        "intent": intent.to_dict(),
                    }
                else:
                    fill_px = px * (1 + slip) if intent.side == "BUY" else px * (1 - slip)
                    row = {
                        "status": "filled",
                        "symbol": intent.symbol,
                        "side": intent.side,
                        "price": round(fill_px, 4),
                        "reference_price": round(px, 4),
                        "slippage_bps": slippage_bps,
                        "notional_ratio": intent.suggested_notional_ratio,
                        "filled_at": datetime.now().isoformat(),
                        "dry_run": intent.dry_run,
                    }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                fills.append(row)
        return {"path": str(path), "count": len(fills), "fills": fills}
