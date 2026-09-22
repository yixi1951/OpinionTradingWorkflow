"""Market quote enrichment and symbol display names."""

from __future__ import annotations

from pathlib import Path

from opinion_trading.core.market_quotes import (
    clear_quote_cache,
    enrich_rows_with_market,
    fetch_quotes_batch,
)
from opinion_trading.core.symbol_map import (
    normalize_a_share_symbol,
    primary_display_name,
)


def test_normalize_a_share_symbol():
    assert normalize_a_share_symbol("600519") == "600519.SH"
    assert normalize_a_share_symbol("000001") == "000001.SZ"
    assert normalize_a_share_symbol("600519.SH") == "600519.SH"


def test_primary_display_name_from_alias_map():
    assert primary_display_name("600519.SH") == "贵州茅台"
    assert primary_display_name("999999.SH") == ""


def test_fetch_quotes_batch_eastmoney_mock(monkeypatch):
    clear_quote_cache()

    def fake_get(url, params=None, headers=None, timeout=0):
        class Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "data": {
                        "diff": [
                            {
                                "f12": "600519",
                                "f14": "贵州茅台",
                                "f2": 1688.88,
                                "f3": 1.23,
                                "f4": 20.5,
                                "f124": 1726982400000,
                            }
                        ]
                    }
                }

        return Resp()

    monkeypatch.setattr(
        "opinion_trading.core.market_quotes.requests.get",
        fake_get,
    )
    quotes = fetch_quotes_batch(["600519.SH"], force_refresh=True)
    q = quotes["600519.SH"]
    assert q["ok"] is True
    assert q["name"] == "贵州茅台"
    assert q["last_price"] == 1688.88
    assert q["change_pct"] == 1.23
    assert q["source"] == "eastmoney_ulist"


def test_enrich_rows_with_market(monkeypatch):
    clear_quote_cache()
    monkeypatch.setattr(
        "opinion_trading.core.market_quotes.fetch_quotes_batch",
        lambda symbols, **kwargs: {
            "600519.SH": {
                "symbol": "600519.SH",
                "name": "贵州茅台",
                "last_price": 100.0,
                "change_pct": 0.5,
                "change_amount": 0.5,
                "as_of": "2026-06-17T15:00:00+08:00",
                "market_status": "closed",
                "source": "eastmoney_ulist",
                "delayed": True,
                "ok": True,
            }
        },
    )
    rows = enrich_rows_with_market([{"symbol": "600519", "score": 0.9}])
    assert rows[0]["symbol"] == "600519.SH"
    assert rows[0]["name"] == "贵州茅台"
    assert rows[0]["quote"]["last_price"] == 100.0


def test_dashboard_snapshot_enriched(monkeypatch, tmp_path: Path):
    report = tmp_path / "reports"
    report.mkdir()
    (report / "realtime_picks_20260101_120000.csv").write_text(
        "symbol,rank,score\n600519.SH,1,0.5\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("REPORT_DIR", str(report))
    monkeypatch.setenv("MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setattr(
        "opinion_trading.core.market_quotes.fetch_quotes_batch",
        lambda symbols, **kwargs: {
            "600519.SH": {
                "symbol": "600519.SH",
                "name": "贵州茅台",
                "last_price": 10.0,
                "change_pct": 0.1,
                "change_amount": 0.01,
                "as_of": None,
                "market_status": "closed",
                "source": "test",
                "delayed": True,
                "ok": True,
            }
        },
    )
    from opinion_trading.services import api_app

    client = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(api_app.app)
    snap = client.get("/v1/dashboard/snapshot").json()
    assert snap["ok"] is True
    assert snap["picks"][0]["name"] == "贵州茅台"
    assert snap["picks"][0]["quote"]["last_price"] == 10.0

    q = client.get("/v1/quotes", params={"symbols": "600519.SH"}).json()
    assert q["ok"] is True
    assert "600519.SH" in q["quotes"]
