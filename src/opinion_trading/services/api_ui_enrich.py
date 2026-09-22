"""Dashboard list enrichment (names + quotes) for API responses."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from opinion_trading.core.market_quotes import enrich_rows_with_market, fetch_quotes_batch
from opinion_trading.core.symbol_map import normalize_a_share_symbol, primary_display_name


def enrich_picks_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    rows = payload.get("picks")
    if not isinstance(rows, list) or not rows:
        return payload
    out = dict(payload)
    out["picks"] = enrich_rows_with_market(rows)
    out["market"] = {"quotes_cached_ttl_sec": 25}
    return out


def quotes_for_symbols(symbols: List[str]) -> Dict[str, Any]:
    normalized = [normalize_a_share_symbol(s) for s in symbols if str(s).strip()]
    normalized = [s for s in normalized if s]
    quotes = fetch_quotes_batch(normalized)
    return {
        "ok": bool(quotes),
        "symbols": normalized,
        "quotes": quotes,
        "market_status": next(iter(quotes.values()), {}).get("market_status") if quotes else None,
    }


def attach_names_only(rows: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Offline-safe name enrichment without network quotes."""
    out: List[Dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        sym = normalize_a_share_symbol(str(data.get("symbol") or ""))
        if sym:
            data["symbol"] = sym
            name = str(data.get("name") or "").strip() or primary_display_name(sym)
            if name:
                data["name"] = name
        out.append(data)
    return out
