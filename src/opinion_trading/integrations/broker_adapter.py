"""Broker / execution adapters — default is paper + signal export only (no live orders)."""

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
    """Normalized intent suitable for manual copy or future broker API."""

    trade_date: str
    symbol: str
    side: str  # BUY | SELL
    confidence: float
    suggested_notional_ratio: float
    reason: str
    source: str = "opinion_trading"
    dry_run: bool = True

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
            "exported_at": datetime.now().isoformat(),
        }


class BaseBrokerAdapter(ABC):
    """Contract for execution adapters. Default implementations are dry-run only."""

    @abstractmethod
    def submit_intents(self, intents: List[ExecutionIntent]) -> Dict[str, object]:
        ...

    def fetch_account(self) -> Dict[str, object]:
        raise NotImplementedError(
            "Live broker account API is not implemented; use paper/sandbox with dry_run=true"
        )

    def fetch_positions(self) -> List[Dict[str, object]]:
        raise NotImplementedError(
            "Live broker positions API is not implemented; use paper state.json"
        )

    def cancel_order(self, order_id: str) -> Dict[str, object]:
        raise NotImplementedError(
            "Live broker cancel API is not implemented"
        )

    def place_live_order(self, intent: ExecutionIntent) -> Dict[str, object]:
        raise NotImplementedError(
            "Live order placement is not implemented; SandboxBrokerAdapter records intents only"
        )


class LiveBrokerAdapter(BaseBrokerAdapter):
    """Explicit stub for future REST/FIX integration — never calls a real API in CI."""

    def __init__(self, report_dir: str = "data/reports") -> None:
        self.report_dir = Path(report_dir)

    def submit_intents(self, intents: List[ExecutionIntent]) -> Dict[str, object]:
        raise NotImplementedError(
            "LiveBrokerAdapter.submit_intents is not wired; enable dry_run and use sandbox/paper"
        )


class PaperBrokerAdapter(BaseBrokerAdapter):
    """Records intents to JSONL; never calls a real exchange."""

    def __init__(self, report_dir: str = "data/reports") -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def submit_intents(self, intents: List[ExecutionIntent]) -> Dict[str, object]:
        if not intents:
            return {"path": "", "count": 0}
        day = intents[0].trade_date
        path = self.report_dir / f"execution_intents_{day}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            for intent in intents:
                f.write(json.dumps(intent.to_dict(), ensure_ascii=False) + "\n")
        return {"path": str(path), "count": len(intents), "dry_run": True}


class SandboxBrokerAdapter(BaseBrokerAdapter):
    """P4 paper/sandbox: records dry-run intents; never places live orders.

    Distinct from ``PaperBrokerAdapter`` only in the audit filename and the
    explicit ``sandbox`` / ``live_order=False`` flags. A real broker API is
    still required for production matching.
    """

    def __init__(self, report_dir: str = "data/reports") -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.recorded: List[Dict] = []

    def submit_intents(self, intents: List[ExecutionIntent]) -> Dict[str, object]:
        if not intents:
            return {
                "path": "",
                "count": 0,
                "dry_run": True,
                "sandbox": True,
                "live_order": False,
            }
        day = intents[0].trade_date
        path = self.report_dir / f"sandbox_intents_{day}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            for intent in intents:
                payload = intent.to_dict()
                payload["sandbox"] = True
                payload["live_order"] = False
                self.recorded.append(payload)
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return {
            "path": str(path),
            "count": len(intents),
            "dry_run": True,
            "sandbox": True,
            "live_order": False,
        }


class SignalExportAdapter(BaseBrokerAdapter):
    """CSV export for external OMS / manual trading (still dry-run)."""

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


def get_broker_adapter(name: str, report_dir: str) -> BaseBrokerAdapter:
    key = (name or "paper").lower()
    if key in ("export", "csv"):
        return SignalExportAdapter(report_dir)
    if key in ("sandbox", "paper_sandbox", "dry_run"):
        return SandboxBrokerAdapter(report_dir)
    return PaperBrokerAdapter(report_dir)
