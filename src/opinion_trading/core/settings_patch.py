"""Safe partial updates to config/settings.yaml (universe symbols)."""

from __future__ import annotations

from pathlib import Path
from typing import List

try:
    import yaml  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


def parse_symbol_list(text: str) -> List[str]:
    lines = [ln.strip() for ln in (text or "").replace(",", "\n").splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def update_explanation_lang(config_path: str, lang: str) -> None:
    if yaml is None:
        raise ModuleNotFoundError("PyYAML required")
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(config_path)
    code = "en" if (lang or "").lower().startswith("en") else "zh"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    project = raw.setdefault("project", {})
    project["explanation_lang"] = code
    path.write_text(
        yaml.dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def set_analysis_enabled(config_path: str, enabled: bool) -> None:
    if yaml is None:
        raise ModuleNotFoundError("PyYAML required")
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(config_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    analysis = raw.setdefault("analysis", {})
    analysis["enabled"] = bool(enabled)
    path.write_text(
        yaml.dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def update_universe_symbols(config_path: str, symbols: List[str]) -> None:
    if yaml is None:
        raise ModuleNotFoundError("PyYAML required")
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(config_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    universe = raw.setdefault("universe", {})
    universe["symbols"] = symbols
    path.write_text(
        yaml.dump(raw, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
