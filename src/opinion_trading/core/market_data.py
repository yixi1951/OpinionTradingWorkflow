"""Unified market data interface with caching and multi-source fallback.

Priority: yfinance → akshare → local CSV cache.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

_MARKET_CACHE_DIR: Path | None = None
_CACHE_TTL_HOURS = 4
# Shared Eval / paper-equity close table (date, symbol, close).
_LOCAL_PRICE_DF: pd.DataFrame | None = None


def _get_cache_dir() -> Path:
    global _MARKET_CACHE_DIR
    if _MARKET_CACHE_DIR is None:
        d = os.environ.get("MARKET_CACHE_DIR", "data/market_cache")
        _MARKET_CACHE_DIR = Path(d)
        _MARKET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _MARKET_CACHE_DIR


def _cache_key(symbol: str, interval: str = "1d") -> str:
    safe = symbol.replace(".", "_").replace("=", "_")
    return f"{safe}_{interval}.parquet"


def _read_cache(symbol: str, interval: str = "1d") -> pd.DataFrame | None:
    cache_dir = _get_cache_dir()
    key = _cache_key(symbol, interval)
    path = cache_dir / key
    if not path.exists():
        return None
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours > _CACHE_TTL_HOURS:
        logger.debug("Market cache expired for %s (%.1f h)", symbol, age_hours)
        return None
    try:
        df = pd.read_parquet(path)
        logger.debug("Market cache HIT %s", symbol)
        return df
    except Exception:
        return None


def _write_cache(symbol: str, df: pd.DataFrame, interval: str = "1d") -> None:
    if df.empty:
        return
    try:
        cache_dir = _get_cache_dir()
        key = _cache_key(symbol, interval)
        df.to_parquet(cache_dir / key)
    except Exception as exc:
        logger.warning("Failed to write market cache for %s: %s", symbol, exc)


def _to_tz_naive(df: pd.DataFrame) -> pd.DataFrame:
    """Strip timezone info so DataFrames are consistently naive."""
    if df.empty:
        return df
    df = df.copy()
    for col in df.columns:
        if hasattr(df[col], "dtype") and hasattr(df[col].dtype, "tz") and df[col].dtype.tz is not None:
            try:
                df[col] = df[col].dt.tz_localize(None)
            except Exception:
                try:
                    df[col] = df[col].dt.tz_convert(None)
                except Exception:
                    pass
    return df


def set_local_price_table(price_df: pd.DataFrame | None) -> None:
    """Install the same close table used by evaluate_signals (P1 alignment)."""
    global _LOCAL_PRICE_DF
    if price_df is None or price_df.empty:
        _LOCAL_PRICE_DF = None
        return
    from opinion_trading.core.evaluation import normalize_price_frame

    _LOCAL_PRICE_DF = normalize_price_frame(price_df)


def load_local_price_table(price_csv: str | None = None) -> pd.DataFrame:
    """Load a CSV into the process-wide price table and return it."""
    from opinion_trading.core.evaluation import load_prices, resolve_price_csv

    path = resolve_price_csv(price_csv)
    if not Path(path).is_file():
        set_local_price_table(None)
        return pd.DataFrame()
    df = load_prices(path)
    set_local_price_table(df)
    return df


def get_local_price_table() -> pd.DataFrame | None:
    return _LOCAL_PRICE_DF


def _lookup_local_close(symbol: str, trade_date: date) -> tuple[float | None, str]:
    if _LOCAL_PRICE_DF is None or _LOCAL_PRICE_DF.empty:
        return None, "unavailable"
    from opinion_trading.core.evaluation import lookup_close

    px = lookup_close(_LOCAL_PRICE_DF, symbol, trade_date)
    if px is None:
        return None, "unavailable"
    return float(px), "price_table"


# ── Public API ────────────────────────────────────────────────────────────


def fetch_ohlcv(
    symbol: str,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """Fetch OHLCV data with yfinance → akshare fallback.

    Returns columns: [Open, High, Low, Close, Volume] with DatetimeIndex.
    """
    if start_date is None:
        start_date = (date.today() - timedelta(days=365)).isoformat()
    if end_date is None:
        end_date = date.today().isoformat()
    if isinstance(start_date, date):
        start_date = start_date.isoformat()
    if isinstance(end_date, date):
        end_date = end_date.isoformat()

    if use_cache:
        cached = _read_cache(symbol, interval)
        if cached is not None and not cached.empty:
            return cached

    df = _fetch_yfinance(symbol, start_date, end_date, interval)

    if df is None or df.empty:
        df = _fetch_akshare(symbol, start_date, end_date, interval)

    if df is not None and not df.empty:
        df = _to_tz_naive(df)
        if use_cache:
            _write_cache(symbol, df, interval)
        return df

    logger.warning("No market data available for %s", symbol)
    return pd.DataFrame()


def fetch_current_price(symbol: str) -> float | None:
    """Fetch the latest close price for a symbol."""
    df = fetch_ohlcv(symbol, start_date=(date.today() - timedelta(days=10)).isoformat())
    if df.empty:
        return None
    try:
        return float(df["Close"].iloc[-1])
    except (IndexError, KeyError):
        return None


def fetch_close_on_date(symbol: str, trade_date: date) -> tuple[float | None, str]:
    """Return (close, source) for trade_date using last available bar on or before that date.

    Prefers the Eval price table (PRICE_FILE / cache CSV) so paper equity and
    evaluate_signals mark the same close.
    """
    table_px, table_src = _lookup_local_close(symbol, trade_date)
    if table_px is not None:
        return table_px, table_src

    start = (trade_date - timedelta(days=45)).isoformat()
    end = (trade_date + timedelta(days=5)).isoformat()
    df = fetch_ohlcv(symbol, start_date=start, end_date=end, use_cache=True)
    if df.empty:
        return None, "unavailable"

    work = df.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        if "Date" in work.columns:
            work = work.set_index("Date")
        else:
            return None, "unavailable"
    work = work.sort_index()
    work.index = pd.to_datetime(work.index, errors="coerce").tz_localize(None)
    target = pd.Timestamp(trade_date)
    subset = work[work.index.normalize() <= target]
    if subset.empty:
        return None, "unavailable"
    try:
        px = float(subset["Close"].iloc[-1])
        return px, "market"
    except (IndexError, KeyError, TypeError, ValueError):
        return None, "unavailable"


def fetch_closes_for_symbols(
    symbols: List[str],
    trade_date: date,
) -> Dict[str, tuple[float | None, str]]:
    """Batch close lookup for paper trading (Eval price table first)."""
    if _LOCAL_PRICE_DF is None:
        csv_path = os.environ.get("PRICE_FILE", "").strip()
        if csv_path or Path("data/reports/price_history_cache.csv").is_file():
            try:
                load_local_price_table(csv_path or None)
            except Exception as exc:
                logger.debug("Local price table load skipped: %s", exc)
    out: Dict[str, tuple[float | None, str]] = {}
    for sym in symbols:
        out[sym] = fetch_close_on_date(sym, trade_date)
    return out


def fetch_multi_ohlcv(
    symbols: List[str],
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    interval: str = "1d",
) -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV for multiple symbols. Returns dict keyed by symbol."""
    result: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = fetch_ohlcv(sym, start_date, end_date, interval)
        if not df.empty:
            result[sym] = df
    return result


# ── Backends ──────────────────────────────────────────────────────────────


def _fetch_yfinance(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
) -> pd.DataFrame | None:
    """Fetch using yfinance. Returns None if unavailable."""
    try:
        import yfinance as yf  # type: ignore[import-not-found]
    except ImportError:
        logger.debug("yfinance not installed, skipping")
        return None

    # Map A-share codes: 600519.SH → 600519.SS, 000001.SZ → 000001.SZ
    yf_symbol = _to_yfinance_symbol(symbol)
    try:
        tk = yf.Ticker(yf_symbol)
        df = tk.history(start=start_date, end=end_date, interval=interval)
        if df.empty:
            logger.debug("yfinance returned empty for %s", symbol)
            return None
        logger.info("yfinance OK %s (%d rows)", symbol, len(df))
        return df
    except Exception as exc:
        logger.debug("yfinance failed for %s: %s", symbol, exc)
        return None


def _fetch_akshare(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
) -> pd.DataFrame | None:
    """Fetch using akshare (A-share specialist). Returns None if unavailable."""
    try:
        import akshare as ak  # type: ignore[import-not-found]
    except ImportError:
        logger.debug("akshare not installed, skipping")
        return None

    if interval != "1d":
        logger.debug("akshare only supports daily interval, requested %s", interval)
        return None

    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol.replace(".SH", "").replace(".SZ", ""),
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        if df.empty:
            return None
        df = df.rename(
            columns={
                "日期": "Date",
                "开盘": "Open",
                "最高": "High",
                "最低": "Low",
                "收盘": "Close",
                "成交量": "Volume",
                "成交额": "Amount",
                "振幅": "Amplitude",
                "涨跌幅": "Change_pct",
                "涨跌额": "Change",
                "换手率": "Turnover",
            }
        )
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        logger.info("akshare OK %s (%d rows)", symbol, len(df))
        return df[["Open", "High", "Low", "Close", "Volume"]]
    except Exception as exc:
        logger.debug("akshare failed for %s: %s", symbol, exc)
        return None


def _to_yfinance_symbol(symbol: str) -> str:
    """Convert A-share codes to yfinance format."""
    s = symbol.upper().strip()
    if s.endswith(".SH"):
        return s.replace(".SH", ".SS")
    if s.endswith(".SZ"):
        return s  # SZ works as-is for yfinance
    return s
