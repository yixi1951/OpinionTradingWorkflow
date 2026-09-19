"""Seed multi-day raw/price fixtures so replay-batch and walk_forward work offline."""

from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

_RAW_PREFIX = "raw_posts_"
_PRICE_FIXTURE = "price_history_replay.csv"
# Calendar span used when expanding dated copies of the template raw CSV.
# ~87 days so default walk-forward 60/20 windows are not shrunk (needed=80).
# Three non-overlapping 60/20 folds would still need ~240 days of history.
FIXTURE_SPAN_START = date(2026, 3, 23)
FIXTURE_SPAN_END = date(2026, 6, 17)
_TEMPLATE_RAW = "raw_posts_2026-06-17.csv"


def repo_root() -> Path:
    """Project root (contains config/, tests/, src/)."""
    return Path(__file__).resolve().parents[3]


def default_fixture_dir() -> Path:
    return repo_root() / "tests" / "fixtures"


def list_fixture_raw_dates(fixture_dir: Optional[str] = None) -> List[str]:
    root = Path(fixture_dir) if fixture_dir else default_fixture_dir()
    if not root.is_dir():
        return []
    dates: List[str] = []
    for path in sorted(root.glob(f"{_RAW_PREFIX}????-??-??.csv")):
        stem = path.stem.replace(_RAW_PREFIX, "")
        if len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
            dates.append(stem)
    return dates


def weekday_span(start: date, end: date) -> List[date]:
    days: List[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def fixture_span() -> Tuple[date, date]:
    return FIXTURE_SPAN_START, FIXTURE_SPAN_END


def _rewrite_raw_template(src: Path, dest: Path, new_date: str) -> None:
    old = src.stem.replace(_RAW_PREFIX, "")
    text = src.read_text(encoding="utf-8")
    dest.write_text(text.replace(old, new_date), encoding="utf-8")


def seed_raw_fixtures(
    raw_dir: str,
    *,
    fixture_dir: Optional[str] = None,
    overwrite: bool = False,
    expand_span: Optional[bool] = None,
) -> List[str]:
    """Copy tests/fixtures/raw_posts_YYYY-MM-DD.csv into raw_dir.

    When ``expand_span`` is true (default for the repo fixture dir), also clone a
    template CSV across weekdays in ``FIXTURE_SPAN_START``..``FIXTURE_SPAN_END``.

    Returns ISO dates that are present in raw_dir after seeding.
    """
    dest = Path(raw_dir)
    dest.mkdir(parents=True, exist_ok=True)
    src_root = Path(fixture_dir) if fixture_dir else default_fixture_dir()
    if expand_span is None:
        try:
            expand_span = src_root.resolve() == default_fixture_dir().resolve()
        except OSError:
            expand_span = False
    copied: List[str] = []
    for date_str in list_fixture_raw_dates(str(src_root)):
        src = src_root / f"{_RAW_PREFIX}{date_str}.csv"
        target = dest / f"{_RAW_PREFIX}{date_str}.csv"
        if target.exists() and not overwrite:
            copied.append(date_str)
            continue
        shutil.copy2(src, target)
        copied.append(date_str)
        logger.info("Seeded raw fixture %s -> %s", src.name, target)

    if expand_span:
        template = src_root / _TEMPLATE_RAW
        if not template.is_file():
            dated = list_fixture_raw_dates(str(src_root))
            if dated:
                template = src_root / f"{_RAW_PREFIX}{dated[-1]}.csv"
        if template.is_file():
            for d in weekday_span(FIXTURE_SPAN_START, FIXTURE_SPAN_END):
                date_str = d.isoformat()
                target = dest / f"{_RAW_PREFIX}{date_str}.csv"
                if target.exists() and not overwrite:
                    copied.append(date_str)
                    continue
                _rewrite_raw_template(template, target, date_str)
                copied.append(date_str)
        else:
            logger.debug("No raw template to expand span from %s", src_root)

    return sorted(set(copied))


def seed_price_fixture(
    dest_csv: str,
    *,
    fixture_dir: Optional[str] = None,
    overwrite: bool = False,
) -> Optional[str]:
    """Copy the offline price table used by evaluate_signals / walk_forward / paper equity."""
    src_root = Path(fixture_dir) if fixture_dir else default_fixture_dir()
    src = src_root / _PRICE_FIXTURE
    if not src.is_file():
        logger.warning("Price fixture missing: %s", src)
        return None
    dest = Path(dest_csv)
    if dest.exists() and not overwrite:
        return str(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    logger.info("Seeded price fixture %s -> %s", src.name, dest)
    return str(dest)


def ensure_replay_inputs(
    raw_dir: str,
    report_dir: str,
    *,
    fixture_dir: Optional[str] = None,
    overwrite: bool = False,
) -> dict:
    """Ensure raw CSVs and a price cache exist (fixture fallback when live data is absent)."""
    from opinion_trading.core.paper_equity import discover_raw_trade_dates

    dates = discover_raw_trade_dates(raw_dir)
    seeded_raw = False
    if not dates:
        dates = seed_raw_fixtures(
            raw_dir, fixture_dir=fixture_dir, overwrite=overwrite
        )
        seeded_raw = True
    price_dest = str(Path(report_dir) / "price_history_cache.csv")
    price_path = seed_price_fixture(
        price_dest, fixture_dir=fixture_dir, overwrite=overwrite
    )
    return {
        "dates": dates,
        "seeded_raw": seeded_raw,
        "price_path": price_path,
    }
