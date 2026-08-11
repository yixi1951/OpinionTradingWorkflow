"""APScheduler-based job runner for daily / post-market tasks."""

from __future__ import annotations

import logging
import os
from datetime import date

from opinion_trading.core.log_utils import configure_logging, get_logger

logger = get_logger(__name__)


def job_premarket_signals() -> None:
    """盘前：采集 + 计算舆情信号."""
    logger.info("scheduler: premarket signals start")
    try:
        from opinion_trading.services.clients import collector_client, compute_client

        trade_date = date.today().isoformat()
        try:
            collector_client().post("/v1/collect", {"trade_date": trade_date})
        except Exception as exc:
            logger.warning("collect failed (isolated): %s", exc)
        compute_client().post(
            "/v1/compute/daily",
            {"trade_date": trade_date, "fast_daily": True, "top_n": 5},
        )
        logger.info("scheduler: premarket signals done")
    except Exception as exc:
        logger.exception("premarket job failed: %s", exc)
        _notify(f"premarket job failed: {exc}")


def job_postmarket_factors() -> None:
    """盘后：计算当日因子表现."""
    logger.info("scheduler: postmarket factors start")
    try:
        from opinion_trading.services.clients import compute_client

        compute_client().post(
            "/v1/compute/factors",
            {"price_file": os.environ.get("PRICE_FILE", "data/reports/price_history_template.csv")},
        )
        logger.info("scheduler: postmarket factors done")
    except Exception as exc:
        logger.exception("postmarket job failed: %s", exc)
        _notify(f"postmarket job failed: {exc}")


def _notify(message: str) -> None:
    try:
        from opinion_trading.core.alert_notifier import AlertNotifier

        AlertNotifier().push_alert(
            {
                "symbol": "SCHEDULER",
                "severity": "red",
                "direction": "down",
                "delta": 0.0,
                "previous_score": 0.0,
                "current_score": 0.0,
                "time": date.today().isoformat(),
            }
        )
        logger.error(message)
    except Exception:
        logger.error("notify failed: %s", message)


def job_health_watchdog() -> None:
    """Periodic health probe → alert on down services / high failure gauges."""
    from opinion_trading.services.clients import (
        api_client,
        collector_client,
        compute_client,
        inference_client,
    )

    down = []
    for name, fn in (
        ("api", api_client),
        ("collector", collector_client),
        ("inference", inference_client),
        ("compute", compute_client),
    ):
        try:
            body = fn().get("/health")
            if body.get("status") != "ok":
                down.append(name)
        except Exception:
            down.append(name)
    if down:
        _notify(f"services down: {','.join(down)}")


def create_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "APScheduler required: pip install apscheduler"
        ) from exc

    tz = os.environ.get("TZ", "Asia/Shanghai")
    sched = BackgroundScheduler(timezone=tz)
    # 交易日盘前 08:30
    sched.add_job(
        job_premarket_signals,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=30),
        id="premarket_signals",
        replace_existing=True,
    )
    # 盘后 16:00 因子
    sched.add_job(
        job_postmarket_factors,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=0),
        id="postmarket_factors",
        replace_existing=True,
    )
    # 每 5 分钟健康巡检
    sched.add_job(
        job_health_watchdog,
        IntervalTrigger(minutes=5),
        id="health_watchdog",
        replace_existing=True,
    )
    return sched


def main() -> None:
    configure_logging()
    sched = create_scheduler()
    sched.start()
    logger.info("APScheduler started (premarket 08:30 / postmarket 16:00 Asia/Shanghai)")
    # Keep process alive
    import time

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        sched.shutdown()


if __name__ == "__main__":
    main()
