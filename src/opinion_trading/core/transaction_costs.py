"""A-share-style transaction cost scaffold (research approximation; not tax/legal advice).

When ``execution.transaction_costs.enabled`` is false (default), callers keep
legacy ``fee_bps`` / ``slippage_bps`` behavior unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Union

import pandas as pd

DateLike = Union[date, datetime, pd.Timestamp, str, None]


@dataclass(frozen=True)
class CommissionTier:
    """One-way commission rate in bps for notionals at or above ``min_notional_cny``."""

    min_notional_cny: float
    commission_bps: float


@dataclass(frozen=True)
class StampTaxEntry:
    """Seller-only stamp duty (印花税) rate from ``effective_from`` onward (inclusive)."""

    effective_from: date
    sell_stamp_bps: float


@dataclass
class TransactionCostConfig:
    """Optional tier commission + stamp-tax calendar overlay on ``fee_bps``."""

    enabled: bool = False
    commission_tiers: List[CommissionTier] = field(default_factory=list)
    stamp_tax_calendar: List[StampTaxEntry] = field(default_factory=list)
    min_commission_cny: float = 0.0
    transfer_fee_bps: float = 0.0

    def summary(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "commission_tiers": len(self.commission_tiers),
            "stamp_tax_entries": len(self.stamp_tax_calendar),
            "min_commission_cny": self.min_commission_cny,
            "transfer_fee_bps": self.transfer_fee_bps,
        }


def _parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        ts = pd.Timestamp(value)
        if pd.isna(ts):
            return None
        return ts.date()
    except (TypeError, ValueError):
        return None


def _default_stamp_calendar() -> List[StampTaxEntry]:
    """Illustrative mainland A-share stamp-duty steps (research only)."""
    return [
        StampTaxEntry(date(2008, 4, 24), 10.0),
        StampTaxEntry(date(2023, 8, 28), 5.0),
    ]


def _default_commission_tiers() -> List[CommissionTier]:
    return [
        CommissionTier(0.0, 2.5),
        CommissionTier(50_000.0, 1.8),
        CommissionTier(200_000.0, 1.2),
    ]


def load_transaction_cost_config(raw: Optional[dict] = None) -> TransactionCostConfig:
    import os

    exec_raw = (raw or {}).get("execution", {}) or {}
    block = exec_raw.get("transaction_costs", {}) or {}
    env_on = os.environ.get("TRANSACTION_COSTS", "").strip().lower()
    enabled = bool(block.get("enabled", False))
    if env_on in ("1", "true", "yes", "on"):
        enabled = True
    elif env_on in ("0", "false", "no", "off"):
        enabled = False

    tiers_raw = block.get("commission_tiers")
    if tiers_raw is None:
        tiers = _default_commission_tiers()
    else:
        tiers = [
            CommissionTier(
                float(row.get("min_notional_cny", 0)),
                float(row.get("commission_bps", 0)),
            )
            for row in tiers_raw
            if isinstance(row, dict)
        ]
        tiers.sort(key=lambda t: t.min_notional_cny)

    stamp_raw = block.get("stamp_tax_calendar")
    if stamp_raw is None:
        stamp_entries = _default_stamp_calendar()
    else:
        stamp_entries = []
        for row in stamp_raw:
            if not isinstance(row, dict):
                continue
            eff = _parse_date(row.get("effective_from"))
            if eff is None:
                continue
            stamp_entries.append(
                StampTaxEntry(eff, float(row.get("sell_stamp_bps", 0)))
            )
        stamp_entries.sort(key=lambda e: e.effective_from)

    return TransactionCostConfig(
        enabled=enabled,
        commission_tiers=tiers,
        stamp_tax_calendar=stamp_entries,
        min_commission_cny=float(block.get("min_commission_cny", 0.0)),
        transfer_fee_bps=float(block.get("transfer_fee_bps", 0.0)),
    )


def commission_bps_for_notional(
    notional_cny: float, tiers: Sequence[CommissionTier]
) -> float:
    if not tiers:
        return 0.0
    notion = max(0.0, float(notional_cny))
    chosen = tiers[0].commission_bps
    for tier in tiers:
        if notion >= tier.min_notional_cny:
            chosen = tier.commission_bps
    return float(chosen)


def stamp_tax_bps_for_sell(
    trade_date: DateLike, calendar: Sequence[StampTaxEntry]
) -> float:
    if not calendar:
        return 0.0
    d = _parse_date(trade_date)
    if d is None:
        return 0.0
    rate = 0.0
    for entry in calendar:
        if d >= entry.effective_from:
            rate = entry.sell_stamp_bps
    return float(rate)


def apply_minimum_commission_bps(
    fee_bps: float, notional_cny: float, min_commission_cny: float
) -> float:
    """Raise effective bps when tier commission would fall below minimum (CNY)."""
    notion = max(0.0, float(notional_cny))
    if notion <= 0 or min_commission_cny <= 0:
        return float(fee_bps)
    implied = notion * float(fee_bps) / 10_000.0
    if implied >= min_commission_cny:
        return float(fee_bps)
    return float(min_commission_cny) / notion * 10_000.0


def resolve_one_way_fee_bps(
    base_fee_bps: float,
    *,
    trade_date: DateLike = None,
    action: str = "BUY",
    config: Optional[TransactionCostConfig] = None,
    notional_cny: float = 0.0,
) -> float:
    """Total one-way fee bps = base ``fee_bps`` + optional tier + seller stamp."""
    total = max(0.0, float(base_fee_bps))
    if config is None or not config.enabled:
        return total
    total += commission_bps_for_notional(notional_cny, config.commission_tiers)
    total += max(0.0, float(config.transfer_fee_bps))
    if config.min_commission_cny > 0:
        total = apply_minimum_commission_bps(
            total, notional_cny, config.min_commission_cny
        )
    if str(action).upper() == "SELL":
        total += stamp_tax_bps_for_sell(trade_date, config.stamp_tax_calendar)
    return total
