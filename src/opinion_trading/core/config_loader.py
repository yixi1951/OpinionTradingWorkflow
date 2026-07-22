from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    import yaml  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

from opinion_trading.core.models import (
    AnalysisConfig,
    ExecutionConfig,
    QualityConfig,
    RiskConfig,
    RuntimeConfig,
    StrategyConfig,
    SentimentRecencyConfig,
    WalkForwardConfig,
)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise ModuleNotFoundError(
            "PyYAML is required. Install with: pip install -r requirements.txt"
        )
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_runtime_config(config_path: str = "config/settings.yaml") -> RuntimeConfig:
    raw = _load_yaml(Path(config_path))

    strategy = raw["strategy"]
    storage = raw["storage"]

    strategy_config = StrategyConfig(
        platforms=strategy["platforms"],
        platform_weights={
            k: float(v) for k, v in strategy.get("platform_weights", {}).items()
        },
        bearish_threshold=float(strategy["bearish_threshold"]),
        bullish_threshold=float(strategy["bullish_threshold"]),
        min_platforms_for_signal=int(strategy["min_platforms_for_signal"]),
        reversal_min_delta=float(strategy["reversal_min_delta"]),
        initial_cash=float(strategy["initial_cash"]),
        position_size_ratio=float(strategy["position_size_ratio"]),
    )

    scoring = raw.get("scoring", {})
    analysis_raw = raw.get("analysis", {})

    if analysis_raw.get("enabled", False):
        analysis_config = AnalysisConfig(
            enabled=True,
            min_analysts=int(analysis_raw.get("min_analysts", 2)),
            bullish_threshold=float(analysis_raw.get("bullish_threshold", 0.20)),
            bearish_threshold=float(analysis_raw.get("bearish_threshold", -0.20)),
            sentiment_weight=float(analysis_raw.get("sentiment_weight", 0.40)),
            technical_weight=float(analysis_raw.get("technical_weight", 0.35)),
            fundamental_weight=float(analysis_raw.get("fundamental_weight", 0.25)),
            max_kelly_fraction=float(analysis_raw.get("max_kelly_fraction", 0.25)),
            min_confidence=float(analysis_raw.get("min_confidence", 0.30)),
            technical_lookback_days=int(analysis_raw.get("technical_lookback_days", 365)),
        )
    else:
        analysis_config = None

    quality_raw = raw.get("quality", {})
    quality_config = QualityConfig(
        enabled=bool(quality_raw.get("enabled", True)),
        max_fallback_rate=float(quality_raw.get("max_fallback_rate", 0.35)),
        max_noise_rate=float(quality_raw.get("max_noise_rate", 0.10)),
        fail_confidence_multiplier=float(
            quality_raw.get("fail_confidence_multiplier", 0.55)
        ),
        block_signals_on_severe_failure=bool(
            quality_raw.get("block_signals_on_severe_failure", True)
        ),
        entity_match_rate_min=float(quality_raw.get("entity_match_rate_min", 0.70)),
    )

    exec_raw = raw.get("execution", {})
    execution_config = ExecutionConfig(
        mode=str(exec_raw.get("mode", "paper")),
        export_intents=bool(exec_raw.get("export_intents", True)),
        dry_run=bool(exec_raw.get("dry_run", True)),
        simulation_slippage_bps=float(exec_raw.get("simulation_slippage_bps", 5.0)),
    )

    risk_raw = raw.get("risk", {})
    risk_config = RiskConfig(
        max_daily_loss_pct=float(risk_raw.get("max_daily_loss_pct", 0.05)),
        max_single_symbol_notional_pct=float(
            risk_raw.get("max_single_symbol_notional_pct", 0.25)
        ),
        max_open_positions=int(risk_raw.get("max_open_positions", 10)),
    )

    rec_raw = raw.get("sentiment_recency", {})
    sentiment_recency_config = SentimentRecencyConfig(
        enabled=bool(rec_raw.get("enabled", True)),
        half_life_hours=float(rec_raw.get("half_life_hours", 24.0)),
    )

    wf_raw = raw.get("walk_forward", {})
    walk_forward_config = WalkForwardConfig(
        enabled_in_evaluate=bool(wf_raw.get("enabled_in_evaluate", True)),
        n_folds=int(wf_raw.get("n_folds", 3)),
        train_days=int(wf_raw.get("train_days", 60)),
        test_days=int(wf_raw.get("test_days", 20)),
    )

    expl_lang = str(raw.get("project", {}).get("explanation_lang", "zh")).strip() or "zh"

    return RuntimeConfig(
        strategy=strategy_config,
        symbols=list(raw["universe"]["symbols"]),
        memory_dir=storage["memory_dir"],
        report_dir=storage["report_dir"],
        raw_dir=storage.get("raw_dir", "data/raw"),
        scoring_mode=str(scoring.get("mode", "hybrid")),
        row_level_llm=bool(scoring.get("row_level_llm", False)),
        max_posts=int(scoring.get("max_posts", 20)),
        analysis=analysis_config,
        quality=quality_config,
        execution=execution_config,
        walk_forward=walk_forward_config,
        sentiment_recency=sentiment_recency_config,
        risk=risk_config,
        explanation_lang=expl_lang,
    )
