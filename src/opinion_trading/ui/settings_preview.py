"""Read-only settings snapshot for Streamlit (no file writes, no secrets)."""

from __future__ import annotations

from typing import Any, Dict

from opinion_trading.core.models import RuntimeConfig


def build_settings_preview(cfg: RuntimeConfig) -> Dict[str, Any]:
    """Serialize safe, high-signal runtime config for sidebar preview."""
    exec_cfg = cfg.execution
    quality = cfg.quality
    winsor = quality.sentiment_winsorize if quality else None
    paper_exit = exec_cfg.paper_exit if exec_cfg else None
    tx = exec_cfg.transaction_costs if exec_cfg else None
    rec = cfg.sentiment_recency
    cross = cfg.cross_day_dedup
    wf = cfg.walk_forward

    preview: Dict[str, Any] = {
        "config_path": "config/settings.yaml",
        "universe_symbol_count": len(cfg.symbols),
        "universe_symbols_sample": list(cfg.symbols[:12]),
        "scoring_mode": cfg.scoring_mode,
        "row_level_llm": cfg.row_level_llm,
        "analysis_enabled": bool(cfg.analysis and cfg.analysis.enabled),
        "execution": {
            "mode": exec_cfg.mode if exec_cfg else "paper",
            "dry_run": exec_cfg.dry_run if exec_cfg else True,
            "simulation_slippage_bps": (
                exec_cfg.simulation_slippage_bps if exec_cfg else 0.0
            ),
            "fee_bps": exec_cfg.fee_bps if exec_cfg else 0.0,
            "paper_exit_enabled": bool(paper_exit and paper_exit.enabled),
            "transaction_costs": tx.summary() if tx else {"enabled": False},
        },
        "risk": {
            "max_daily_loss_pct": cfg.risk.max_daily_loss_pct if cfg.risk else 0.05,
            "max_single_symbol_notional_pct": (
                cfg.risk.max_single_symbol_notional_pct if cfg.risk else 0.25
            ),
            "max_open_positions": cfg.risk.max_open_positions if cfg.risk else 10,
        },
        "sentiment_recency": {
            "enabled": bool(rec and rec.enabled),
            "half_life_hours": rec.half_life_hours if rec else 24.0,
        },
        "quality": {
            "enabled": bool(quality and quality.enabled),
            "sentiment_winsorize_enabled": bool(winsor and winsor.enabled),
        },
        "cross_day_dedup_enabled": bool(cross and cross.enabled),
        "walk_forward_enabled_in_evaluate": bool(
            wf and wf.enabled_in_evaluate
        ),
        "memory_recall": {
            "recall_enabled": bool(cfg.memory and cfg.memory.recall_enabled),
            "recall_auto": bool(cfg.memory and cfg.memory.recall_auto),
            "lookback_days": cfg.memory.lookback_days if cfg.memory else 14,
        },
    }
    return preview
