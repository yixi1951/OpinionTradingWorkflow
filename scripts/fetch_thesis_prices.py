"""Fetch daily closes for thesis symbols into data/reports/price_history_cache.csv.

Prefer akshare Tencent source (stock_zh_a_hist_tx) which is more reliable than
eastmoney hist in this environment.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from crawl_guba_api_bulk import load_symbols  # noqa: E402


def _tx_symbol(symbol: str) -> str:
    code, market = symbol.upper().split(".", maxsplit=1)
    return f"{'sh' if market == 'SH' else 'sz'}{code}"


def fetch_one(symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
    import akshare as ak

    start_c = start.replace("-", "")
    end_c = end.replace("-", "")
    # 1) Tencent
    try:
        df = ak.stock_zh_a_hist_tx(
            symbol=_tx_symbol(symbol),
            start_date=start_c,
            end_date=end_c,
        )
        if df is not None and not df.empty:
            out = pd.DataFrame(
                {
                    "date": pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "close": df["close"].astype(float),
                }
            )
            return out
    except Exception as exc:
        print(f"  tx fail: {exc}")

    # 2) eastmoney hist with retries
    code = symbol.split(".", maxsplit=1)[0]
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                start_date=start_c,
                end_date=end_c,
                adjust="qfq",
            )
            if df is not None and not df.empty:
                return pd.DataFrame(
                    {
                        "date": pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d"),
                        "symbol": symbol,
                        "close": df["收盘"].astype(float),
                    }
                )
        except Exception as exc:
            print(f"  hist fail attempt {attempt+1}: {exc}")
            time.sleep(1.5 * (attempt + 1))
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config" / "settings.yaml"))
    parser.add_argument("--start", default="2026-09-01")
    parser.add_argument("--end", default="")
    parser.add_argument("--with-extra-symbols", action="store_true")
    parser.add_argument(
        "--out",
        default=str(ROOT / "data" / "reports" / "price_history_cache.csv"),
    )
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()

    end = args.end or pd.Timestamp.today().strftime("%Y-%m-%d")
    symbols = load_symbols(Path(args.config), with_extra=args.with_extra_symbols)
    out_path = Path(args.out)

    frames = []
    if out_path.exists():
        try:
            old = pd.read_csv(out_path)
            frames.append(old)
            print(f"Loaded existing cache: {len(old)} rows")
        except Exception:
            pass

    ok = 0
    for i, sym in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] prices {sym} ...", flush=True)
        part = fetch_one(sym, args.start, end)
        if part is None or part.empty:
            print("  empty")
            continue
        frames.append(part)
        ok += 1
        print(f"  +{len(part)} rows")
        time.sleep(args.delay)

    if not frames:
        print("No price data fetched.")
        return
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["date", "symbol"], keep="last")
    combined = combined.sort_values(["symbol", "date"]).reset_index(drop=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_path, index=False)
    print(
        f"Wrote {out_path}: {len(combined)} rows, "
        f"{combined.symbol.nunique()} symbols, "
        f"{combined.date.min()} -> {combined.date.max()} (ok={ok})"
    )


if __name__ == "__main__":
    main()
