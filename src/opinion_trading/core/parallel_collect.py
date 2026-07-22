"""Parallel raw post collection (I/O bound)."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[int, int, str, str, int], None]


def collect_raw_posts_parallel(
    provider: Any,
    symbols: List[str],
    platforms: List[str],
    trade_date: date,
    *,
    max_workers: int | None = None,
    progress_callback: Optional[ProgressCallback] = None,
    progress_log_path: str | None = None,
) -> List[Dict[str, Any]]:
    tasks: List[Tuple[str, str]] = [
        (symbol, platform) for symbol in symbols for platform in platforms
    ]
    if not tasks:
        return []
    workers = max_workers
    if workers is None:
        workers = int(os.environ.get("COLLECT_MAX_WORKERS", "6"))
    workers = max(1, min(workers, len(tasks)))
    total = len(tasks)
    done = 0

    logger.info(
        "Parallel collect start: %d tasks, %d workers, date=%s",
        total,
        workers,
        trade_date.isoformat(),
    )

    log_path: Path | None = None
    if progress_log_path:
        log_path = Path(progress_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    use_tqdm = os.environ.get("COLLECT_SHOW_PROGRESS", "0").lower() in (
        "1",
        "true",
        "yes",
    )
    pbar = None
    if use_tqdm:
        try:
            from tqdm import tqdm

            pbar = tqdm(total=total, desc="collect", unit="task")
        except ImportError:
            pbar = None

    rows: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                provider.collect_raw_posts,
                platform=platform,
                symbol=symbol,
                trade_date=trade_date,
            ): (symbol, platform)
            for symbol, platform in tasks
        }
        for fut in as_completed(futures):
            symbol, platform = futures[fut]
            n_rows = 0
            try:
                part = fut.result()
                n_rows = len(part)
                rows.extend(part)
            except Exception as exc:
                logger.warning(
                    "Parallel collect failed %s/%s: %s", platform, symbol, exc
                )
            done += 1
            logger.info(
                "Collect [%d/%d] %s/%s → %d rows",
                done,
                total,
                platform,
                symbol,
                n_rows,
            )
            if progress_callback:
                progress_callback(done, total, symbol, platform, n_rows)
            if log_path is not None:
                rec = {
                    "time": datetime.now().isoformat(),
                    "done": done,
                    "total": total,
                    "platform": platform,
                    "symbol": symbol,
                    "rows": n_rows,
                }
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if pbar is not None:
                pbar.update(1)
                pbar.set_postfix_str(f"{platform}/{symbol}")

    if pbar is not None:
        pbar.close()
    logger.info("Parallel collect done: %d rows from %d tasks", len(rows), total)
    return rows