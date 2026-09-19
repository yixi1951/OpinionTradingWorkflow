from __future__ import annotations

from opinion_trading.core.config_loader import load_runtime_config
from opinion_trading.ui.settings_preview import build_settings_preview


def test_build_settings_preview_no_secrets():
    cfg = load_runtime_config("config/settings.yaml")
    preview = build_settings_preview(cfg)
    assert "DEEPSEEK" not in str(preview).upper()
    assert preview["universe_symbol_count"] == len(cfg.symbols)
    assert "execution" in preview
    assert preview["execution"]["transaction_costs"]["enabled"] is False
    assert preview["scoring_mode"]
