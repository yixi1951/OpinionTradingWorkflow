import yaml

from opinion_trading.core.config_loader import load_runtime_config
from opinion_trading.core.models import StrategyConfig


def test_load_runtime_config(tmp_path):
    cfg = {
        "strategy": {
            "platforms": ["guba"],
            "platform_weights": {"guba": 1.0},
            "bearish_threshold": -0.6,
            "bullish_threshold": 0.6,
            "min_platforms_for_signal": 1,
            "reversal_min_delta": 0.1,
            "initial_cash": 10000,
            "position_size_ratio": 0.1,
        },
        "universe": {"symbols": ["600519.SH"]},
        "storage": {"memory_dir": "data/memory", "report_dir": "data/reports"},
    }

    p = tmp_path / "settings.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    rc = load_runtime_config(str(p))
    assert isinstance(rc.strategy, StrategyConfig)
    assert rc.strategy.bearish_threshold == -0.6
    assert rc.symbols == ["600519.SH"]
    assert rc.memory_dir == "data/memory"
