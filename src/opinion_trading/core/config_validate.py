"""Startup config validation + environment layering helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Sequence

from opinion_trading.core.models import RuntimeConfig


ALLOWED_ENVS = frozenset({"dev", "staging", "prod"})


@dataclass
class ConfigValidationResult:
    ok: bool
    errors: List[str]
    warnings: List[str]

    def raise_if_invalid(self) -> None:
        if not self.ok:
            raise ValueError("; ".join(self.errors))


def app_env() -> str:
    raw = (os.environ.get("APP_ENV") or os.environ.get("ENV") or "dev").strip().lower()
    return raw if raw in ALLOWED_ENVS else "dev"


def validate_runtime_config(cfg: RuntimeConfig) -> ConfigValidationResult:
    errors: List[str] = []
    warnings: List[str] = []
    env = app_env()

    if not cfg.symbols:
        errors.append("universe.symbols must be non-empty")
    if not cfg.strategy.platforms:
        errors.append("strategy.platforms must be non-empty")

    if not (0 < cfg.strategy.position_size_ratio <= 1):
        errors.append("strategy.position_size_ratio must be in (0, 1]")
    if cfg.strategy.initial_cash <= 0:
        errors.append("strategy.initial_cash must be > 0")
    if cfg.strategy.bullish_threshold <= cfg.strategy.bearish_threshold:
        errors.append("bullish_threshold must be > bearish_threshold")

    risk = cfg.risk
    if risk:
        if not (0 < risk.max_daily_loss_pct <= 0.5):
            errors.append("risk.max_daily_loss_pct must be in (0, 0.5]")
        if not (0 < risk.max_single_symbol_notional_pct <= 1):
            errors.append("risk.max_single_symbol_notional_pct must be in (0, 1]")
        if risk.max_open_positions < 1:
            errors.append("risk.max_open_positions must be >= 1")
        if getattr(risk, "max_concurrent_orders", 1) < 1:
            errors.append("risk.max_concurrent_orders must be >= 1")
        if not (0 < getattr(risk, "max_single_trade_loss_pct", 0.03) <= 0.5):
            errors.append("risk.max_single_trade_loss_pct must be in (0, 0.5]")

    scoring = (cfg.scoring_mode or "").lower()
    env_mode = (os.environ.get("SCORING_MODE") or "").strip().lower()
    if env_mode:
        scoring = env_mode
    if scoring not in {"ai", "hybrid", "keyword", "openclaw", "llm"}:
        warnings.append(f"unknown scoring_mode={scoring!r}")

    llm_endpoint = bool(
        os.environ.get("OPENCLAW_URL")
        or os.environ.get("OPENCLAW_GATEWAY_URL")
        or os.environ.get("INFERENCE_URL")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("QWEN_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
    )
    allow_kw = (os.environ.get("ALLOW_KEYWORD_FALLBACK") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if scoring in {"ai", "openclaw", "llm", "hybrid"} and not llm_endpoint and not allow_kw:
        msg = (
            f"scoring.mode={scoring} requires OPENCLAW_URL (or DEEPSEEK_API_KEY / "
            "INFERENCE_URL). Set SCORING_MODE=keyword or ALLOW_KEYWORD_FALLBACK=1 only "
            "for offline demos."
        )
        if env in {"staging", "prod"}:
            errors.append(msg)
        else:
            warnings.append(msg)

    if env == "prod":
        exec_cfg = cfg.execution
        if exec_cfg and not exec_cfg.dry_run and (exec_cfg.mode or "").lower() not in {
            "paper",
            "export",
            "simulation",
            "sandbox",
        }:
            errors.append("prod forbids non-paper live broker modes without explicit allowlist")
        if os.environ.get("KILL_SWITCH", "").strip() in {"1", "true", "yes"}:
            warnings.append("KILL_SWITCH is active — all new orders will be rejected")
        if not llm_endpoint:
            if scoring in {"ai", "openclaw", "llm", "hybrid"}:
                errors.append("prod AI scoring requires OpenClaw/LLM endpoint")
            else:
                warnings.append("prod without LLM/OpenClaw endpoint — sentiment may be keyword-only")

    if env == "staging" and cfg.browser_enabled and not os.environ.get("XUEQIU_COOKIE"):
        warnings.append("staging browser collect without XUEQIU_COOKIE may yield empty xueqiu")

    return ConfigValidationResult(ok=not errors, errors=errors, warnings=warnings)


def require_env_keys(keys: Sequence[str], *, env: str | None = None) -> List[str]:
    """Return list of missing required env keys for the given APP_ENV."""
    target = (env or app_env()).lower()
    missing = []
    for k in keys:
        if not os.environ.get(k, "").strip():
            missing.append(k)
    if target == "dev":
        return []  # soft in dev
    return missing
