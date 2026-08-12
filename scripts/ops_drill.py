#!/usr/bin/env python3
"""Ops drill: pipeline halt flag + ops alerts (research platform)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.alert_notifier import AlertNotifier
from opinion_trading.core.env_bootstrap import load_dotenv_if_present
from opinion_trading.core.memory_store import JsonLineMemoryStore
from opinion_trading.core.risk_controls import (
    clear_trading_halt,
    is_trading_halted,
    set_kill_switch,
)


def main() -> int:
    load_dotenv_if_present(ROOT)
    if "OPS_ALERTS_ENABLED" not in os.environ:
        os.environ["OPS_ALERTS_ENABLED"] = "1"

    memory_dir = ROOT / "data" / "memory"
    report_dir = ROOT / "data" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    store = JsonLineMemoryStore(str(memory_dir))
    notifier = AlertNotifier()
    results: dict = {}

    prev_ks = os.environ.get("KILL_SWITCH")
    state = store.load_state()
    state = set_kill_switch(state, True, reason="ops_drill")
    store.save_state(state)
    halted, reason = is_trading_halted(state)
    results["halt_on"] = {"halted": halted, "reason": reason}
    results["alert_halt"] = notifier.push_ops_alert(
        "pipeline_halted",
        severity="critical",
        summary=f"ops_drill:{reason}",
        trade_date=datetime.now().date().isoformat(),
    )

    state = set_kill_switch(store.load_state(), False)
    state = clear_trading_halt(state)
    store.save_state(state)
    if prev_ks is None:
        os.environ.pop("KILL_SWITCH", None)
    else:
        os.environ["KILL_SWITCH"] = prev_ks
    halted2, reason2 = is_trading_halted(state)
    results["halt_off"] = {"halted": halted2, "reason": reason2}

    ok = bool(results["halt_on"]["halted"]) and not bool(results["halt_off"]["halted"])
    results["ok"] = ok
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = report_dir / f"ops_drill_{ts}.json"
    out.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(f"Wrote {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
