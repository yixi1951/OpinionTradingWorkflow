#!/usr/bin/env python3
"""Materialize compact synthetic ~240-day history for 3-fold 60/20 walk-forward.

Writes prices + signal_history into a tmp directory. Optionally clones weekday
raw CSVs from the committed template. Does **not** add 170+ raw files to git.

Research prototype only — not real market or crawl history.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.replay_fixtures import materialize_honest_walk_forward


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        default="/tmp/ot-honest-wf",
        help="Directory for generated prices / signals / optional raw CSVs",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Also clone weekday raw_posts_*.csv from the fixture template",
    )
    args = parser.parse_args()
    info = materialize_honest_walk_forward(args.dest, include_raw=args.include_raw)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
