"""CLI: DeepSeek live sentiment probe (not used by CI).

Without a key (expected in CI / offline):
  PYTHONPATH=src python scripts/probe_deepseek.py
  → DEEPSEEK NOT_CONFIGURED  (exit 2; --soft exits 0)

With a key (local only):
  DEEPSEEK_API_KEY=sk-... PYTHONPATH=src python scripts/probe_deepseek.py
  DEEPSEEK_API_KEY=sk-... PYTHONPATH=src python scripts/probe_deepseek.py --score-sample
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from opinion_trading.core.env_bootstrap import load_dotenv_if_present  # noqa: E402

load_dotenv_if_present(ROOT)


def main() -> None:
    from opinion_trading.core.deepseek_client import run_cli

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
