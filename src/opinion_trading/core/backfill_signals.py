"""P0: Replay fast-daily over many raw CSV dates to grow signal_history for walk-forward."""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from opinion_trading.agents.workflow import OpinionTradingWorkflow
from opinion_trading.core.paper_equity import discover_raw_trade_dates
from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)


def run_replay_batch(
    config_path: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    raw_dir: Optional[str] = None,
    reset_paper: bool = False,
    seed_fixtures: bool = True,
) -> Dict[str, object]:
    """Run --fast-daily for each date that has raw_posts_<date>.csv."""
    from opinion_trading.core.config_loader import load_runtime_config
    from opinion_trading.core.market_data import load_local_price_table
    from opinion_trading.core.replay_fixtures import ensure_replay_inputs

    runtime = load_runtime_config(config_path)
    rdir = raw_dir or runtime.raw_dir
    dates = discover_raw_trade_dates(rdir)
    seeded_raw = False
    if not dates and seed_fixtures:
        info = ensure_replay_inputs(rdir, runtime.report_dir)
        dates = list(info.get("dates") or [])
        seeded_raw = bool(info.get("seeded_raw"))
        logger.info(
            "No live raw CSVs; seeded %d fixture dates from tests/fixtures",
            len(dates),
        )
    if start_date:
        dates = [d for d in dates if d >= start_date]
    if end_date:
        dates = [d for d in dates if d <= end_date]

    try:
        load_local_price_table()
    except Exception as exc:
        logger.debug("Price table load skipped: %s", exc)

    if reset_paper:
        from pathlib import Path
        import json

        mem = Path(runtime.memory_dir)
        mem.mkdir(parents=True, exist_ok=True)
        init = {
            "cash": runtime.strategy.initial_cash,
            "positions": {},
            "last_run_date": None,
        }
        (mem / "state.json").write_text(
            json.dumps(init, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    workflow = OpinionTradingWorkflow(config_path=config_path)
    results: List[Dict] = []
    total_signals = 0

    for d in dates:
        run_date = date.fromisoformat(d)
        try:
            out = workflow.run_daily(run_date, skip_crawl=True)
            n_sig = int(out.get("signals", 0))
            total_signals += n_sig
            results.append(
                {
                    "date": d,
                    "signals": n_sig,
                    "trades": int(out.get("trades", 0)),
                    "ok": True,
                }
            )
            logger.info("Replay %s: signals=%d trades=%d", d, n_sig, out.get("trades", 0))
        except FileNotFoundError as exc:
            results.append({"date": d, "ok": False, "error": str(exc)})
            logger.warning("Replay skip %s: %s", d, exc)
        except Exception as exc:
            results.append({"date": d, "ok": False, "error": str(exc)})
            logger.exception("Replay failed %s", d)

    return {
        "run_time": datetime.now().isoformat(),
        "dates_run": len([r for r in results if r.get("ok")]),
        "dates_total": len(dates),
        "total_signals": total_signals,
        "seeded_raw": seeded_raw,
        "results": results,
    }
