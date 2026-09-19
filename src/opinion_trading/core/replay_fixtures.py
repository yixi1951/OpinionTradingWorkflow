"""Seed multi-day raw/price fixtures so replay-batch and walk_forward work offline."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

_RAW_PREFIX = "raw_posts_"
_PRICE_FIXTURE = "price_history_replay.csv"


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


def seed_raw_fixtures(
    raw_dir: str,
    *,
    fixture_dir: Optional[str] = None,
    overwrite: bool = False,
) -> List[str]:
    """Copy tests/fixtures/raw_posts_YYYY-MM-DD.csv into raw_dir.

    Returns ISO dates that are present in raw_dir after seeding.
    """
    dest = Path(raw_dir)
    dest.mkdir(parents=True, exist_ok=True)
    src_root = Path(fixture_dir) if fixture_dir else default_fixture_dir()
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
