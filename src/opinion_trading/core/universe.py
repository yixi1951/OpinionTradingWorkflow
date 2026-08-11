"""Universe helpers: HS300 / CSI500 constituent loading with offline seed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from opinion_trading.core.log_utils import get_logger
from opinion_trading.core.symbol_map import SEED_ALIAS_MAP

logger = get_logger(__name__)

# Default focused pool: liquid names with dense sentiment coverage expectation
DEFAULT_FOCUS_UNIVERSE: List[str] = list(SEED_ALIAS_MAP.keys())

INDEX_CODES = {
    "hs300": "000300",
    "csi300": "000300",
    "csi500": "000905",
    "zz500": "000905",
}


def _normalize_symbol(code: str, exchange: str = "") -> str:
    c = str(code).strip()
    if "." in c:
        return c.upper()
    # 6-digit
    if len(c) == 6 and c.isdigit():
        ex = exchange.upper()
        if ex in {"SH", "SSE", "XSHG"} or "SHANGHAI" in ex or "上海" in exchange:
            return f"{c}.SH"
        if ex in {"SZ", "SZSE", "XSHE"} or "SHENZHEN" in ex or "深圳" in exchange:
            return f"{c}.SZ"
        if c.startswith(("5", "6", "9")):
            return f"{c}.SH"
        return f"{c}.SZ"
    return c.upper()


def load_index_constituents(
    index: str = "hs300",
    *,
    cache_path: str = "data/universe",
    max_symbols: int = 50,
    use_akshare: bool = True,
) -> List[str]:
    """Load index constituents; fall back to seed focus universe offline.

    For student-scale pipelines we cap at ``max_symbols`` (default 50) to keep
    crawl volume tractable while still covering liquid HS300 names.
    """
    key = INDEX_CODES.get(index.lower(), index)
    cache_dir = Path(cache_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"constituents_{key}.json"

    symbols: List[str] = []
    if use_akshare:
        try:
            import akshare as ak  # type: ignore

            df = ak.index_stock_cons_csindex(symbol=key)
            # Prefer constituent code column over index code column
            code_col = None
            name_col = None
            for c in df.columns:
                cs = str(c)
                if "成分" in cs and "代码" in cs:
                    code_col = c
                elif code_col is None and ("成分" in cs and "code" in cs.lower()):
                    code_col = c
                if "成分" in cs and "名称" in cs:
                    name_col = c
            if code_col is None:
                # positional fallback: csindex schema often puts constituent code at col 4
                for c in df.columns:
                    sample = str(df[c].iloc[0]) if len(df) else ""
                    if len(sample) == 6 and sample.isdigit() and sample != key:
                        code_col = c
                        break
            if code_col is None:
                raise ValueError(f"cannot locate constituent code column: {list(df.columns)}")

            exch_col = None
            for c in df.columns:
                if "交易所" in str(c) and "英文" not in str(c):
                    exch_col = c
                    break

            symbols = []
            alias_extra: Dict[str, List[str]] = {}
            for _, row in df.iterrows():
                code = str(row[code_col]).strip()
                exch = str(row[exch_col]) if exch_col is not None else ""
                if "上海" in exch or "SSE" in exch.upper() or "Shanghai" in exch:
                    sym = _normalize_symbol(code, "SH")
                elif "深圳" in exch or "SZSE" in exch.upper() or "Shenzhen" in exch:
                    sym = _normalize_symbol(code, "SZ")
                else:
                    sym = _normalize_symbol(code)
                if sym.endswith(".SH") or sym.endswith(".SZ"):
                    # skip pure index codes
                    if code == key:
                        continue
                    symbols.append(sym)
                    if name_col is not None:
                        nm = str(row[name_col]).strip()
                        if nm:
                            alias_extra[sym] = [nm, code]
            if alias_extra:
                try:
                    from opinion_trading.core.symbol_map import get_symbol_mapper

                    get_symbol_mapper().extend(alias_extra)
                except Exception:
                    pass
            symbols = list(dict.fromkeys(symbols))
            cache_file.write_text(
                json.dumps(symbols, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info("Loaded %d constituents for %s via akshare", len(symbols), key)
        except Exception as exc:
            logger.warning("akshare index load failed (%s): %s", key, exc)

    if not symbols and cache_file.exists():
        try:
            symbols = json.loads(cache_file.read_text(encoding="utf-8"))
            logger.info("Loaded %d constituents from cache %s", len(symbols), cache_file)
        except Exception:
            symbols = []

    if not symbols:
        # Prefer seed names that are typically in HS300
        symbols = list(DEFAULT_FOCUS_UNIVERSE)
        logger.info("Using seed focus universe (%d symbols)", len(symbols))

    # Prioritize seed liquid names then fill from index
    prioritized = [s for s in DEFAULT_FOCUS_UNIVERSE if s in set(symbols)]
    rest = [s for s in symbols if s not in set(prioritized)]
    ordered = prioritized + rest
    return ordered[: max(1, int(max_symbols))]


def ensure_universe_file(
    path: str = "config/universe_focus.json",
    index: str = "hs300",
    max_symbols: int = 30,
) -> List[str]:
    """Write/read a focused universe file for settings sync."""
    target = Path(path)
    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8"))
        return list(data.get("symbols") or DEFAULT_FOCUS_UNIVERSE)[:max_symbols]
    symbols = load_index_constituents(index, max_symbols=max_symbols)
    payload = {
        "index": index,
        "max_symbols": max_symbols,
        "symbols": symbols,
        "note": "Focused subset for dense sentiment coverage (not full market).",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return symbols


def merge_universe_with_settings_symbols(
    settings_symbols: Sequence[str],
    *,
    prefer_index: bool = False,
    index: str = "hs300",
    max_symbols: int = 30,
) -> List[str]:
    if prefer_index:
        return load_index_constituents(index, max_symbols=max_symbols)
    base = [str(s).strip().upper() for s in settings_symbols if str(s).strip()]
    if len(base) >= 5:
        return base[:max_symbols]
    filled = load_index_constituents(index, max_symbols=max_symbols)
    return list(dict.fromkeys(base + filled))[:max_symbols]
