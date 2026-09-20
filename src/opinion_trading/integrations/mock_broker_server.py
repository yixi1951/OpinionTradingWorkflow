"""Local HTTP mock broker for dry-run order intent testing (no real exchange).

Start with:
  PYTHONPATH=src python -m opinion_trading.integrations.mock_broker_server

Or ``scripts/run_mock_broker.py``. Not used in CI except via in-process TestClient.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="OpinionTrading Mock Broker", version="0.1.0")

_STORE: Dict[str, Dict[str, Any]] = {}


class IntentPayload(BaseModel):
    trade_date: str
    symbol: str
    side: str
    confidence: float = 0.0
    suggested_notional_ratio: float = 0.0
    reason: str = ""
    source: str = "opinion_trading"
    dry_run: bool = True
    client_order_id: Optional[str] = None


class SubmitBatch(BaseModel):
    intents: List[IntentPayload] = Field(default_factory=list)
    dry_run: bool = True
    live_order: bool = False


def _stable_order_id(intent: IntentPayload) -> str:
    if intent.client_order_id:
        return intent.client_order_id
    blob = json.dumps(
        {
            "trade_date": intent.trade_date,
            "symbol": intent.symbol,
            "side": intent.side,
            "source": intent.source,
        },
        sort_keys=True,
    )
    return "mock-" + hashlib.sha256(blob.encode()).hexdigest()[:16]


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "mock_broker_sandbox"}


@app.get("/v1/orders/{order_id}")
def get_order(order_id: str) -> Dict[str, Any]:
    rec = _STORE.get(order_id)
    if not rec:
        raise HTTPException(status_code=404, detail="order not found")
    return rec


@app.post("/v1/intents")
def submit_intents(batch: SubmitBatch) -> Dict[str, Any]:
    if batch.live_order and not batch.dry_run:
        # Mock never simulates funded live trading — reject explicitly.
        raise HTTPException(
            status_code=403,
            detail="live_order rejected: mock broker is dry-run only",
        )
    fills: List[Dict[str, Any]] = []
    rejects: List[Dict[str, Any]] = []
    for intent in batch.intents:
        oid = _stable_order_id(intent)
        if oid in _STORE:
            fills.append(_STORE[oid])
            continue
        side = str(intent.side).upper()
        if side not in ("BUY", "SELL"):
            rejects.append(
                {"order_id": oid, "reason": f"invalid side {intent.side}"}
            )
            continue
        if intent.suggested_notional_ratio <= 0:
            rejects.append(
                {"order_id": oid, "reason": "suggested_notional_ratio must be > 0"}
            )
            continue
        record = {
            "order_id": oid,
            "status": "filled",
            "trade_date": intent.trade_date,
            "symbol": intent.symbol,
            "side": side,
            "filled_qty": 100,
            "fill_price": 10.0,
            "dry_run": True,
            "live_order": False,
            "sandbox": True,
            "filled_at": datetime.now(timezone.utc).isoformat(),
        }
        _STORE[oid] = record
        fills.append(record)
    return {
        "dry_run": True,
        "live_order": False,
        "sandbox": True,
        "fills": fills,
        "rejects": rejects,
        "count": len(fills),
    }


def reset_store() -> None:
    """Test helper."""
    _STORE.clear()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
