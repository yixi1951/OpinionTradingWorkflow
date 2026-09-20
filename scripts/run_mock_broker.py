#!/usr/bin/env python3
"""Run the local HTTP mock broker (dry-run only)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("PYTHONPATH", "src")

from opinion_trading.integrations.mock_broker_server import main

if __name__ == "__main__":
    main()
