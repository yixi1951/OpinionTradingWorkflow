#!/usr/bin/env python3
"""Re-enable multi-agent analysis after CI/smoke disabled it."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.settings_patch import set_analysis_enabled  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=str(ROOT / "config" / "settings.yaml"),
        help="Path to settings.yaml",
    )
    parser.add_argument(
        "--off",
        action="store_true",
        help="Disable analysis instead of enabling",
    )
    args = parser.parse_args()
    set_analysis_enabled(args.config, enabled=not args.off)
    state = "disabled" if args.off else "enabled"
    print(f"analysis.enabled = {state} in {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())