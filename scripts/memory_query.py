#!/usr/bin/env python3
"""Thin CLI wrapper for historical memory query/recall."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.config_loader import load_runtime_config  # noqa: E402
from opinion_trading.core.historical_memory import (  # noqa: E402
    format_query_table,
    query_memory,
    recall_symbol_context,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query JSONL historical memory")
    parser.add_argument(
        "--config", default="config/settings.yaml", help="Settings YAML path"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    q = sub.add_parser("query", help="Filtered JSONL rows")
    q.add_argument(
        "--kind",
        default="sentiment",
        choices=["signals", "sentiment", "trades", "events", "quality_gate"],
    )
    q.add_argument("--symbol", default=None)
    q.add_argument("--start-date", default=None)
    q.add_argument("--end-date", default=None)
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--format", choices=["json", "table"], default="json")

    r = sub.add_parser("recall", help="Compact symbol context")
    r.add_argument("--symbol", required=True)
    r.add_argument("--lookback-days", type=int, default=14)

    args = parser.parse_args()
    cfg = load_runtime_config(args.config)

    if args.command == "query":
        rows = query_memory(
            cfg.memory_dir,
            kind=args.kind,
            symbol=args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
        )
        if args.format == "table":
            print(format_query_table(rows))
        else:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    ctx = recall_symbol_context(
        cfg.memory_dir,
        args.symbol,
        lookback_days=args.lookback_days,
    )
    print(json.dumps(ctx, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
