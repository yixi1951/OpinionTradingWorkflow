"""CLI: probe crawl proxies from collection.proxy_urls / PROXY_POOL.

Empty pool (CI / default settings):
  PYTHONPATH=src python scripts/check_proxy_health.py
  → PROXY HEALTH PASS  (skip, no proxies)

With a pool (still mockable; this script does short HTTP GETs):
  PROXY_POOL=http://127.0.0.1:8888 PYTHONPATH=src python scripts/check_proxy_health.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))


def main() -> None:
    from opinion_trading.core.proxy_health import run_cli

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
