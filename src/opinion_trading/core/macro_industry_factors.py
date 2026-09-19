"""Stub industry / macro factor slots for multi-agent consensus (offline neutral)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Sequence

from opinion_trading.agents.analyst_base import AnalystOpinion


@dataclass
class MacroIndustryFactorConfig:
    enabled: bool = False
    industry_weight: float = 0.0
    macro_weight: float = 0.0


def load_macro_industry_factor_config(
    raw: Optional[dict] = None,
) -> MacroIndustryFactorConfig:
    import os

    analysis = (raw or {}).get("analysis", {}) or {}
    block = analysis.get("macro_industry_factors", {}) or {}
    env_on = os.environ.get("MACRO_INDUSTRY_FACTORS", "").strip().lower()
    enabled = bool(block.get("enabled", False))
    if env_on in ("1", "true", "yes", "on"):
        enabled = True
    elif env_on in ("0", "false", "no", "off"):
        enabled = False
    return MacroIndustryFactorConfig(
        enabled=enabled,
        industry_weight=float(block.get("industry_weight", 0.0)),
        macro_weight=float(block.get("macro_weight", 0.0)),
    )


def stub_industry_opinion(symbol: str, trade_date: date) -> AnalystOpinion:
    """Placeholder industry factor — always neutral until real data is wired."""
    return AnalystOpinion(
        symbol=str(symbol),
        trade_date=trade_date,
        analyst_name="industry",
        score=0.0,
        confidence=0.05,
        reasoning="[STUB] industry factor slot — neutral placeholder (no live industry feed).",
    )


def stub_macro_opinion(symbol: str, trade_date: date) -> AnalystOpinion:
    """Placeholder macro factor — always neutral."""
    return AnalystOpinion(
        symbol=str(symbol),
        trade_date=trade_date,
        analyst_name="macro",
        score=0.0,
        confidence=0.05,
        reasoning="[STUB] macro factor slot — neutral placeholder (no live macro feed).",
    )


def append_stub_factor_opinions(
    opinions: List[AnalystOpinion],
    *,
    symbols: Sequence[str],
    trade_date: date,
    config: MacroIndustryFactorConfig,
) -> List[AnalystOpinion]:
    if not config.enabled:
        return opinions
    out = list(opinions)
    for sym in symbols:
        if config.industry_weight > 0:
            out.append(stub_industry_opinion(sym, trade_date))
        if config.macro_weight > 0:
            out.append(stub_macro_opinion(sym, trade_date))
    return out


def factor_weight_overrides(config: MacroIndustryFactorConfig) -> Dict[str, float]:
    """Optional consensus weight entries (zero until enabled with positive weights)."""
    if not config.enabled:
        return {}
    weights: Dict[str, float] = {}
    if config.industry_weight > 0:
        weights["industry"] = config.industry_weight
    if config.macro_weight > 0:
        weights["macro"] = config.macro_weight
    return weights
