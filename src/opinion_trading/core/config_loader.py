from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    import yaml  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

from opinion_trading.core.models import RuntimeConfig, StrategyConfig


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise ModuleNotFoundError("PyYAML is required. Install with: pip install -r requirements.txt")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_runtime_config(config_path: str = "config/settings.yaml") -> RuntimeConfig:
    raw = _load_yaml(Path(config_path))

    strategy = raw["strategy"]
    storage = raw["storage"]

    strategy_config = StrategyConfig(
        platforms=strategy["platforms"],
        platform_weights={k: float(v) for k, v in strategy.get("platform_weights", {}).items()},
        bearish_threshold=float(strategy["bearish_threshold"]),
        bullish_threshold=float(strategy["bullish_threshold"]),
        min_platforms_for_signal=int(strategy["min_platforms_for_signal"]),
        reversal_min_delta=float(strategy["reversal_min_delta"]),
        initial_cash=float(strategy["initial_cash"]),
        position_size_ratio=float(strategy["position_size_ratio"]),
    )

    return RuntimeConfig(
        strategy=strategy_config,
        symbols=list(raw["universe"]["symbols"]),
        memory_dir=storage["memory_dir"],
        report_dir=storage["report_dir"],
        raw_dir=storage.get("raw_dir", "data/raw"),
    )
