"""Fundamental metrics fetcher with caching.

Uses yfinance for broad market coverage (US/HK) and falls back to
akshare for A-share specific fundamentals.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict


from opinion_trading.core.log_utils import get_logger

logger = get_logger(__name__)

_FUND_CACHE_DIR: Path | None = None
_FUND_CACHE_TTL_HOURS = 24  # fundamentals change slowly


def _get_cache_dir() -> Path:
    global _FUND_CACHE_DIR
    if _FUND_CACHE_DIR is None:
        d = os.environ.get("FUND_CACHE_DIR", "data/fund_cache")
        _FUND_CACHE_DIR = Path(d)
        _FUND_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _FUND_CACHE_DIR


def _cache_key(symbol: str) -> str:
    return symbol.replace(".", "_").replace("=", "_") + "_fund.json"


def _read_cache(symbol: str) -> Dict[str, Any] | None:
    cache_dir = _get_cache_dir()
    path = cache_dir / _cache_key(symbol)
    if not path.exists():
        return None
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours > _FUND_CACHE_TTL_HOURS:
        return None
    try:
        import json
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(symbol: str, data: Dict[str, Any]) -> None:
    try:
        import json
        cache_dir = _get_cache_dir()
        path = cache_dir / _cache_key(symbol)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Failed to write fund cache for %s: %s", symbol, exc)


# ── Public API ────────────────────────────────────────────────────────────


def fetch_fundamentals(symbol: str, use_cache: bool = True) -> Dict[str, Any]:
    """Fetch key fundamental metrics for a symbol.

    Returns dict with keys: pe, pb, roe, market_cap, revenue_growth,
    debt_to_equity, dividend_yield, sector, industry, name, currency.
    Missing fields are None.
    """
    if use_cache:
        cached = _read_cache(symbol)
        if cached is not None:
            return cached

    data = _fetch_yfinance_fundamentals(symbol)
    if not data or data.get("pe") is None:
        data_ak = _fetch_akshare_fundamentals(symbol)
        if data_ak:
            data = {**(data or {}), **data_ak}

    if data:
        _write_cache(symbol, data)
    return data or {}


def _fetch_yfinance_fundamentals(symbol: str) -> Dict[str, Any]:
    """Fetch fundamentals via yfinance."""
    try:
        import yfinance as yf  # type: ignore[import-not-found]
    except ImportError:
        return {}

    yf_symbol = _to_yfinance_symbol(symbol)
    try:
        tk = yf.Ticker(yf_symbol)
        info = tk.info or {}
    except Exception as exc:
        logger.debug("yfinance info failed for %s: %s", symbol, exc)
        return {}

    return {
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "pe": info.get("trailingPE") or info.get("forwardPE"),
        "pb": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "market_cap": info.get("marketCap"),
        "revenue_growth": info.get("revenueGrowth"),
        "debt_to_equity": info.get("debtToEquity"),
        "dividend_yield": info.get("dividendYield"),
        "profit_margins": info.get("profitMargins"),
        "beta": info.get("beta"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
    }


def _fetch_akshare_fundamentals(symbol: str) -> Dict[str, Any]:
    """A-share specific fundamentals via akshare."""
    try:
        import akshare as ak  # type: ignore[import-not-found]
    except ImportError:
        return {}

    code = symbol.replace(".SH", "").replace(".SZ", "")
    try:
        df = ak.stock_individual_info_em(symbol=code)
        if df.empty:
            return {}
        info: Dict[str, Any] = {}
        for _, row in df.iterrows():
            item = str(row.iloc[0])
            val = row.iloc[1]
            if "市盈率" in item:
                info["pe"] = _try_float(val)
            elif "市净率" in item:
                info["pb"] = _try_float(val)
            elif "总市值" in item:
                info["market_cap"] = _try_float(val) * 1e8
            elif "营业收入" in item and "增长率" in item:
                info["revenue_growth"] = _try_float(val)
        return info
    except Exception as exc:
        logger.debug("akshare fundamentals failed for %s: %s", symbol, exc)
        return {}


def _to_yfinance_symbol(symbol: str) -> str:
    s = symbol.upper().strip()
    if s.endswith(".SH"):
        return s.replace(".SH", ".SS")
    if s.endswith(".SZ"):
        return s
    return s


def _try_float(val: object) -> float | None:
    try:
        return float(str(val).replace(",", "").replace("亿", "e8").replace("万", "e4"))
    except (ValueError, TypeError):
        return None


# ── Scoring ───────────────────────────────────────────────────────────────


def analyst_score(fundamentals: Dict[str, Any]) -> Dict[str, float]:
    """Score a stock based on its fundamentals.

    Returns dict with 'score' (-1 to +1) and sub-scores.
    """
    score = 0.0
    details: Dict[str, float] = {}

    # PE score: low PE is generally better for value
    pe = fundamentals.get("pe")
    if pe is not None and pe > 0:
        if pe < 10:
            pe_score = 0.8
        elif pe < 20:
            pe_score = 0.4
        elif pe < 30:
            pe_score = 0.0
        elif pe < 50:
            pe_score = -0.3
        else:
            pe_score = -0.6
        details["pe_score"] = pe_score
        score += pe_score * 0.25

    # ROE score: higher is better
    roe = fundamentals.get("roe")
    if roe is not None:
        roe_pct = float(roe) * 100
        if roe_pct > 20:
            roe_score = 0.8
        elif roe_pct > 15:
            roe_score = 0.5
        elif roe_pct > 10:
            roe_score = 0.2
        elif roe_pct > 5:
            roe_score = -0.1
        else:
            roe_score = -0.5
        details["roe_score"] = roe_score
        score += roe_score * 0.25

    # Revenue growth
    growth = fundamentals.get("revenue_growth")
    if growth is not None:
        g = float(growth) * 100
        if g > 30:
            g_score = 0.8
        elif g > 15:
            g_score = 0.5
        elif g > 5:
            g_score = 0.2
        elif g > 0:
            g_score = 0.0
        else:
            g_score = -0.5
        details["growth_score"] = g_score
        score += g_score * 0.20

    # Market cap (size stability)
    mc = fundamentals.get("market_cap")
    if mc is not None and mc > 0:
        mc_b = float(mc) / 1e9
        if mc_b > 1000:
            mc_score = 0.3  # mega-cap stability
        elif mc_b > 100:
            mc_score = 0.2
        elif mc_b > 10:
            mc_score = 0.0
        else:
            mc_score = -0.2
        details["market_cap_score"] = mc_score
        score += mc_score * 0.10

    # Beta (risk)
    beta = fundamentals.get("beta")
    if beta is not None:
        b = float(beta)
        if 0.8 <= b <= 1.2:
            beta_score = 0.2  # in line with market
        elif b < 0.5:
            beta_score = 0.3  # defensive
        elif b > 2.0:
            beta_score = -0.5  # very risky
        elif b > 1.5:
            beta_score = -0.2
        else:
            beta_score = 0.0
        details["beta_score"] = beta_score
        score += beta_score * 0.10

    # Profit margin
    pm = fundamentals.get("profit_margins")
    if pm is not None:
        pm_pct = float(pm) * 100
        if pm_pct > 20:
            pm_score = 0.5
        elif pm_pct > 10:
            pm_score = 0.3
        elif pm_pct > 5:
            pm_score = 0.1
        elif pm_pct > 0:
            pm_score = 0.0
        else:
            pm_score = -0.3
        details["margin_score"] = pm_score
        score += pm_score * 0.10

    details["score"] = round(max(-1.0, min(1.0, score)), 4)
    return details
