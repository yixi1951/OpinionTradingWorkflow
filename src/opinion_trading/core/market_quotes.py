"""Near-real-time A-share quote snapshots (Eastmoney-style) with short TTL cache."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import requests

from opinion_trading.core.log_utils import get_logger
from opinion_trading.core.symbol_map import (
    get_symbol_mapper,
    normalize_a_share_symbol,
    primary_display_name,
)

logger = get_logger(__name__)

_EASTMONEY_ULIST = "https://push2.eastmoney.com/api/qt/ulist.np/get"
_QUOTE_TTL_SEC = 25
_BATCH_MAX = 40

_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_cache_meta: Dict[str, Any] = {}


def clear_quote_cache() -> None:
    """Test helper — drop in-memory quote cache."""
    _cache.clear()
    _cache_meta.clear()


def _to_eastmoney_secid(symbol: str) -> str:
    sym = normalize_a_share_symbol(symbol)
    code = sym.split(".", 1)[0]
    if sym.endswith(".SH"):
        return f"1.{code}"
    if sym.endswith(".SZ"):
        return f"0.{code}"
    return f"0.{code}"


def _beijing_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def china_market_status(now: Optional[datetime] = None) -> str:
    """Return ``open`` | ``closed`` | ``lunch`` for China A-share session (Beijing)."""
    ts = now or _beijing_now()
    if ts.weekday() >= 5:
        return "closed"
    minutes = ts.hour * 60 + ts.minute
    morning = 9 * 60 + 30 <= minutes < 11 * 60 + 30
    afternoon = 13 * 60 <= minutes < 15 * 60
    if morning or afternoon:
        return "open"
    if 11 * 60 + 30 <= minutes < 13 * 60:
        return "lunch"
    return "closed"


def _parse_quote_time(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            ts = float(raw)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8))).isoformat()
        text = str(raw).strip()
        if not text:
            return None
        if text.isdigit() and len(text) >= 12:
            # YYYYMMDDHHMMSS
            dt = datetime.strptime(text[:14], "%Y%m%d%H%M%S")
            return dt.replace(tzinfo=timezone(timedelta(hours=8))).isoformat()
    except Exception:
        return None
    return None


def _fetch_eastmoney_ulist(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    if not symbols:
        return {}
    secids = ",".join(_to_eastmoney_secid(s) for s in symbols)
    params = {
        "fltt": "2",
        "invt": "2",
        "secids": secids,
        "fields": "f12,f14,f2,f3,f4,f124,f152",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; OpinionTradingWorkflow/1.0)",
        "Referer": "https://quote.eastmoney.com/",
    }
    try:
        resp = requests.get(_EASTMONEY_ULIST, params=params, headers=headers, timeout=12)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        logger.debug("Eastmoney ulist failed: %s", exc)
        return {}

    diff = ((payload or {}).get("data") or {}).get("diff") or []
    out: Dict[str, Dict[str, Any]] = {}
    mapper = get_symbol_mapper()
    for row in diff:
        if not isinstance(row, Mapping):
            continue
        code = str(row.get("f12") or "").strip()
        if not code:
            continue
        sym = normalize_a_share_symbol(code, mapper=mapper)
        name = str(row.get("f14") or "").strip() or primary_display_name(sym, mapper=mapper)
        last = row.get("f2")
        chg_pct = row.get("f3")
        chg_amt = row.get("f4")
        as_of = _parse_quote_time(row.get("f124")) or _parse_quote_time(row.get("f152"))
        try:
            last_f = float(last) if last not in (None, "-", "") else None
        except (TypeError, ValueError):
            last_f = None
        try:
            pct_f = float(chg_pct) if chg_pct not in (None, "-", "") else None
        except (TypeError, ValueError):
            pct_f = None
        try:
            amt_f = float(chg_amt) if chg_amt not in (None, "-", "") else None
        except (TypeError, ValueError):
            amt_f = None
        session = china_market_status()
        out[sym] = {
            "symbol": sym,
            "name": name,
            "last_price": last_f,
            "change_pct": pct_f,
            "change_amount": amt_f,
            "as_of": as_of,
            "market_status": session,
            "source": "eastmoney_ulist",
            "delayed": session != "open",
            "ok": last_f is not None,
        }
    return out


def _fallback_daily_quote(symbol: str) -> Dict[str, Any]:
    from opinion_trading.core.market_data import fetch_ohlcv

    sym = normalize_a_share_symbol(symbol)
    end = date.today()
    start = end - timedelta(days=14)
    df = fetch_ohlcv(sym, start_date=start.isoformat(), end_date=end.isoformat(), use_cache=True)
    name = primary_display_name(sym)
    base: Dict[str, Any] = {
        "symbol": sym,
        "name": name,
        "last_price": None,
        "change_pct": None,
        "change_amount": None,
        "as_of": None,
        "market_status": china_market_status(),
        "source": "daily_close",
        "delayed": True,
        "ok": False,
    }
    if df is None or df.empty or "Close" not in df.columns:
        base["error"] = "no_price_data"
        return base
    work = df.sort_index()
    try:
        last = float(work["Close"].iloc[-1])
        prev = float(work["Close"].iloc[-2]) if len(work) >= 2 else last
    except (IndexError, KeyError, TypeError, ValueError):
        base["error"] = "parse_error"
        return base
    chg = last - prev
    pct = (chg / prev * 100.0) if prev else None
    idx = work.index[-1]
    as_of = None
    try:
        as_of = pd_timestamp_iso(idx)
    except Exception:
        as_of = str(idx)[:10]
    base.update(
        {
            "last_price": last,
            "change_amount": chg,
            "change_pct": pct,
            "as_of": as_of,
            "ok": True,
            "note": "上一交易日收盘价（非实时）",
        }
    )
    return base


def pd_timestamp_iso(idx: Any) -> str:
    import pandas as pd

    ts = pd.Timestamp(idx)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Shanghai")
    else:
        ts = ts.tz_localize("Asia/Shanghai")
    return ts.isoformat()


def fetch_quote(symbol: str, *, use_cache: bool = True) -> Dict[str, Any]:
    quotes = fetch_quotes_batch([symbol], use_cache=use_cache)
    sym = normalize_a_share_symbol(symbol)
    return quotes.get(sym) or _empty_quote(sym, error="not_found")


def fetch_quotes_batch(
    symbols: Iterable[str],
    *,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> Dict[str, Dict[str, Any]]:
    mapper = get_symbol_mapper()
    normalized: List[str] = []
    seen = set()
    for raw in symbols:
        sym = normalize_a_share_symbol(raw, mapper=mapper)
        if not sym or sym in seen:
            continue
        seen.add(sym)
        normalized.append(sym)

    now = time.time()
    out: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    if use_cache and not force_refresh:
        for sym in normalized:
            hit = _cache.get(sym)
            if hit and (now - hit[0]) <= _QUOTE_TTL_SEC:
                out[sym] = dict(hit[1])
            else:
                missing.append(sym)
    else:
        missing = list(normalized)

    if missing:
        fresh: Dict[str, Dict[str, Any]] = {}
        for i in range(0, len(missing), _BATCH_MAX):
            chunk = missing[i : i + _BATCH_MAX]
            fresh.update(_fetch_eastmoney_ulist(chunk))
        for sym in missing:
            row = fresh.get(sym)
            if row is None or not row.get("ok"):
                row = _fallback_daily_quote(sym)
            if not row.get("name"):
                row["name"] = primary_display_name(sym, mapper=mapper)
            out[sym] = row
            if use_cache:
                _cache[sym] = (now, dict(row))
        _cache_meta["fetched_at"] = datetime.now(timezone.utc).isoformat()
        _cache_meta["source"] = "eastmoney_ulist+daily_fallback"

    return out


def _empty_quote(symbol: str, error: str = "") -> Dict[str, Any]:
    sym = normalize_a_share_symbol(symbol)
    return {
        "symbol": sym,
        "name": primary_display_name(sym),
        "last_price": None,
        "change_pct": None,
        "change_amount": None,
        "as_of": None,
        "market_status": china_market_status(),
        "source": "none",
        "delayed": True,
        "ok": False,
        "error": error or "unavailable",
    }


def enrich_row_with_market(
    row: Mapping[str, Any],
    quotes: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Attach ``name`` and ``quote`` to a pick/symbol row."""
    data = dict(row)
    sym_raw = str(data.get("symbol") or data.get("code") or "").strip()
    sym = normalize_a_share_symbol(sym_raw)
    if sym:
        data["symbol"] = sym
    name = str(data.get("name") or "").strip() or primary_display_name(sym)
    if name:
        data["name"] = name
    qmap = quotes or fetch_quotes_batch([sym] if sym else [])
    quote = qmap.get(sym) if sym else None
    if quote:
        data["quote"] = dict(quote)
        if not data.get("name") and quote.get("name"):
            data["name"] = quote["name"]
    return data


def enrich_rows_with_market(rows: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    syms = [
        normalize_a_share_symbol(str(r.get("symbol") or r.get("code") or ""))
        for r in rows
    ]
    syms = [s for s in syms if s]
    quotes = fetch_quotes_batch(syms)
    return [enrich_row_with_market(r, quotes=quotes) for r in rows]
