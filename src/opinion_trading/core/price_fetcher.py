from __future__ import annotations

from datetime import datetime
from typing import Iterable

import pandas as pd
import requests

try:
    import akshare as ak  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover
    ak = None


def _to_akshare_symbol(symbol: str) -> str:
    sym = symbol.upper()
    if sym.endswith((".SH", ".SZ")):
        return sym.split(".", 1)[0]
    return sym


def _to_eastmoney_secid(symbol: str) -> str:
    sym = symbol.upper()
    code = sym.split(".", 1)[0]
    if sym.endswith(".SH"):
        return f"1.{code}"
    if sym.endswith(".SZ"):
        return f"0.{code}"
    return f"0.{code}"


def _fetch_prices_eastmoney(symbols: Iterable[str], start_date: str, end_date: str) -> pd.DataFrame:
    rows = []
    start_token = start_date.replace("-", "")
    end_token = end_date.replace("-", "")

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params_base = {
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": start_token,
        "end": end_token,
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
    }

    for symbol in symbols:
        secid = _to_eastmoney_secid(symbol)
        params = dict(params_base)
        params["secid"] = secid
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            continue

        klines = ((payload or {}).get("data") or {}).get("klines") or []
        for line in klines:
            parts = str(line).split(",")
            if len(parts) < 3:
                continue
            try:
                rows.append(
                    {
                        "date": pd.to_datetime(parts[0]).strftime("%Y-%m-%d"),
                        "symbol": symbol,
                        "close": float(parts[2]),
                    }
                )
            except Exception:
                continue

    return pd.DataFrame(rows)


def _fetch_prices_akshare(symbols: Iterable[str], start_date: str, end_date: str) -> pd.DataFrame:
    if ak is None:
        return pd.DataFrame()

    rows = []
    start_token = start_date.replace("-", "")
    end_token = end_date.replace("-", "")

    for symbol in symbols:
        ak_symbol = _to_akshare_symbol(symbol)
        try:
            data = ak.stock_zh_a_hist(
                symbol=ak_symbol,
                period="daily",
                start_date=start_token,
                end_date=end_token,
                adjust="",
            )
        except Exception:
            continue

        if data is None or data.empty:
            continue

        date_col = "日期" if "日期" in data.columns else None
        close_col = "收盘" if "收盘" in data.columns else None
        if date_col is None or close_col is None:
            continue

        for _, row in data.iterrows():
            rows.append(
                {
                    "date": pd.to_datetime(row[date_col]).strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "close": float(row[close_col]),
                }
            )

    return pd.DataFrame(rows)


def fetch_prices(symbols: Iterable[str], start_date: str, end_date: str) -> pd.DataFrame:
    eastmoney_df = _fetch_prices_eastmoney(symbols, start_date, end_date)
    if not eastmoney_df.empty:
        return eastmoney_df

    ak_df = _fetch_prices_akshare(symbols, start_date, end_date)
    if not ak_df.empty:
        return ak_df

    return pd.DataFrame()
