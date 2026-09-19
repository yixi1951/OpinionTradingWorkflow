"""CLI: OpenClaw / collection gateway health (HTTP + optional WS).

Offline (no OPENCLAW_URL, or --stub):
  PYTHONPATH=src python scripts/check_gateway_health.py --stub

Live:
  OPENCLAW_URL=http://127.0.0.1:18790 PYTHONPATH=src python scripts/check_gateway_health.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))


def main() -> None:
    from opinion_trading.core.gateway_health import run_cli

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
