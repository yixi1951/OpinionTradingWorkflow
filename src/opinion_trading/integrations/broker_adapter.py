"""Research-only execution adapters — paper / export / sandbox. No live OMS."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from opinion_trading.core.models import TradeSignal


@dataclass
class ExecutionIntent:
    """Normalized research intent for paper simulation or CSV export."""

    trade_date: str
    symbol: str
    side: str  # BUY | SELL
    confidence: float
    suggested_notional_ratio: float
    reason: str
    source: str = "opinion_trading"
    dry_run: bool = True
    request_id: Optional[str] = None
    event_id: Optional[str] = None
    trace_id: Optional[str] = None
    order_id: Optional[str] = None
    quantity: int = 0
    order_type: str = "market"
    limit_price: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "trade_date": self.trade_date,
            "symbol": self.symbol,
            "side": self.side,
            "confidence": self.confidence,
            "suggested_notional_ratio": self.suggested_notional_ratio,
            "reason": self.reason,
            "source": self.source,
            "dry_run": self.dry_run,
            "request_id": self.request_id,
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "order_id": self.order_id,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
            "exported_at": datetime.now().isoformat(),
        }


class BaseBrokerAdapter(ABC):
    @abstractmethod
    def submit_intents(self, intents: List[ExecutionIntent]) -> Dict[str, object]:
        ...


class PaperBrokerAdapter(BaseBrokerAdapter):
    """Records intents to JSONL; never calls a real exchange."""

    def __init__(
        self, report_dir: str = "data/reports", *, idempotency=None, audit=None
    ) -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._seen = set()
        self.idempotency = idempotency
        self.audit = audit

    def submit_intents(self, intents: List[ExecutionIntent]) -> Dict[str, object]:
        if not intents:
            return {"path": "", "count": 0}
        day = intents[0].trade_date
        path = self.report_dir / f"execution_intents_{day}.jsonl"
        written = 0
        skipped = 0
        with path.open("a", encoding="utf-8") as f:
            for intent in intents:
                key = intent.request_id or (
                    f"{intent.trade_date}:{intent.symbol}:{intent.side}:{intent.reason}"
                )
                duplicate = key in self._seen
                if self.idempotency is not None:
                    duplicate = not self.idempotency.remember(
                        "orders",
                        key,
                        payload={"symbol": intent.symbol, "side": intent.side},
                    )
                if duplicate:
                    skipped += 1
                    if self.audit is not None:
                        self.audit.emit(
                            "order_duplicate_skipped",
                            request_id=key,
                            symbol=intent.symbol,
                        )
                    continue
                self._seen.add(key)
                f.write(json.dumps(intent.to_dict(), ensure_ascii=False) + "\n")
                written += 1
                if self.audit is not None:
                    self.audit.emit(
                        "order_submitted",
                        request_id=key,
                        symbol=intent.symbol,
                        side=intent.side,
                        dry_run=True,
                    )
        return {
            "path": str(path),
            "count": written,
            "skipped_duplicate": skipped,
            "dry_run": True,
        }


class SignalExportAdapter(BaseBrokerAdapter):
    """CSV export for offline research review (still dry-run)."""

    def __init__(self, report_dir: str = "data/reports") -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def submit_intents(self, intents: List[ExecutionIntent]) -> Dict[str, object]:
        if not intents:
            return {"path": "", "count": 0}
        import csv

        day = intents[0].trade_date
        path = self.report_dir / f"signals_export_{day}.csv"
        write_header = not path.exists()
        with path.open("a", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "trade_date",
                    "symbol",
                    "side",
                    "confidence",
                    "suggested_notional_ratio",
                    "dry_run",
                ],
            )
            if write_header:
                w.writeheader()
            for intent in intents:
                w.writerow(
                    {
                        "trade_date": intent.trade_date,
                        "symbol": intent.symbol,
                        "side": intent.side,
                        "confidence": intent.confidence,
                        "suggested_notional_ratio": intent.suggested_notional_ratio,
                        "dry_run": intent.dry_run,
                    }
                )
        return {"path": str(path), "count": len(intents), "dry_run": True}


def trade_signals_to_intents(
    signals: List[TradeSignal],
    *,
    position_size_ratio: float = 0.2,
    kelly_by_symbol: Optional[Dict[str, float]] = None,
    dry_run: bool = True,
) -> List[ExecutionIntent]:
    kelly_by_symbol = kelly_by_symbol or {}
    intents: List[ExecutionIntent] = []
    for sig in signals:
        if sig.action not in ("BUY", "SELL"):
            continue
        ratio = kelly_by_symbol.get(sig.symbol, position_size_ratio)
        ratio = max(0.0, min(1.0, float(ratio)))
        intents.append(
            ExecutionIntent(
                trade_date=sig.trade_date.isoformat(),
                symbol=sig.symbol,
                side=sig.action,
                confidence=float(sig.confidence),
                suggested_notional_ratio=ratio,
                reason=sig.reason[:500],
                dry_run=dry_run,
            )
        )
    return intents


def get_broker_adapter(name: str, report_dir: str, **kwargs) -> BaseBrokerAdapter:
    key = (name or "paper").lower()
    if key in ("live", "rest"):
        raise RuntimeError(
            "Live OMS trading is not part of this research query platform. "
            "Use paper, export, or sandbox."
        )
    if key in ("export", "csv"):
        return SignalExportAdapter(report_dir)
    if key in ("sandbox",):
        from opinion_trading.integrations.sandbox_broker import SandboxBrokerAdapter

        return SandboxBrokerAdapter(report_dir, **kwargs)
    return PaperBrokerAdapter(report_dir, **kwargs)
