"""Offline tests for external-track scaffolds (broker HTTP, crawl, labels, auth)."""

from __future__ import annotations

import json

import pytest

from opinion_trading.core.crawl_persistence import (
    append_crawl_journal,
    list_raw_trade_dates,
    prune_raw_csvs,
    summarize_raw_span,
)
from opinion_trading.core.dashboard_auth import OAuthSettings, resolve_auth_backend
from opinion_trading.core.human_labels_workflow import (
    export_unlabeled_from_raw,
    import_human_labels_csv,
)
from opinion_trading.integrations.broker_adapter import ExecutionIntent
from opinion_trading.integrations.http_sandbox_broker import HttpSandboxBrokerAdapter
from opinion_trading.integrations.mock_broker_server import (
    IntentPayload,
    SubmitBatch,
    health,
    reset_store,
    submit_intents as mock_submit_intents,
)


@pytest.fixture(autouse=True)
def _reset_mock_store():
    reset_store()


def test_mock_broker_idempotent_fills():
    batch = SubmitBatch(
        intents=[
            IntentPayload(
                trade_date="2026-06-10",
                symbol="000001.SZ",
                side="BUY",
                suggested_notional_ratio=0.2,
                dry_run=True,
            )
        ],
        dry_run=True,
        live_order=False,
    )
    r1 = mock_submit_intents(batch)
    oid = r1["fills"][0]["order_id"]
    r2 = mock_submit_intents(batch)
    assert r2["fills"][0]["order_id"] == oid
    assert health()["status"] == "ok"


def test_http_sandbox_adapter_records_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_HTTP_BROKER_SANDBOX", "1")
    adapter = HttpSandboxBrokerAdapter(str(tmp_path), base_url="http://fake.local")

    def fake_post(url, json=None, timeout=None):
        class _Resp:
            status_code = 200

            def json(self):
                return {"fills": [], "count": len(json.get("intents", [])), "dry_run": True}

            def raise_for_status(self):
                return None

        return _Resp()

    monkeypatch.setattr(
        "opinion_trading.integrations.http_sandbox_broker.requests.post",
        fake_post,
    )
    intents = [
        ExecutionIntent(
            trade_date="2026-06-10",
            symbol="000001.SZ",
            side="BUY",
            confidence=0.5,
            suggested_notional_ratio=0.1,
            reason="unit",
        )
    ]
    out = adapter.submit_intents(intents)
    assert out["count"] == 1
    assert out["live_order"] is False
    audit = list(tmp_path.glob("http_sandbox_intents_*.jsonl"))
    assert audit


def test_crawl_span_and_prune(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for d in ("2026-06-01", "2026-06-03"):
        (raw / f"raw_posts_{d}.csv").write_text(
            "trade_date,platform,symbol,title\n", encoding="utf-8"
        )
    dates = list_raw_trade_dates(raw)
    assert dates == ["2026-06-01", "2026-06-03"]
    summary = summarize_raw_span(raw)
    assert summary["gap_count"] == 1
    assert summary["gaps"] == ["2026-06-02"]
    # keep_days=1 deletes files strictly older than yesterday (by filename date)
    result = prune_raw_csvs(raw, keep_days=1)
    assert result["deleted_combined"] == 2
    assert list_raw_trade_dates(raw) == []


def test_crawl_journal_append(tmp_path):
    j = tmp_path / "journal.jsonl"
    append_crawl_journal(j, {"trade_date": "2026-06-10", "ok": True})
    lines = j.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["trade_date"] == "2026-06-10"


def test_human_labels_import_export(tmp_path):
    raw = tmp_path / "raw.csv"
    raw.write_text(
        "platform,symbol,trade_date,title,content\n"
        "guba,000001.SZ,2026-06-10,t1,c1\n",
        encoding="utf-8",
    )
    out = tmp_path / "unlabeled.csv"
    info = export_unlabeled_from_raw(raw, out)
    assert info["rows"] == 1
    labeled = tmp_path / "labeled.csv"
    labeled.write_text(
        "id,platform,symbol,trade_date,text,label,notes,label_source,annotator\n"
        "1,guba,000001.SZ,2026-06-10,hello,bull,,human,alice\n",
        encoding="utf-8",
    )
    imp = import_human_labels_csv(labeled, out_path=tmp_path / "clean.csv")
    assert imp["ok"] is True


def test_oauth_settings_and_backend(monkeypatch):
    monkeypatch.setenv("STREAMLIT_AUTH_BACKEND", "oauth")
    assert resolve_auth_backend() == "oauth"
    monkeypatch.setenv("OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("OAUTH_DISCOVERY_URL", "https://example.com/.well-known/openid-configuration")
    cfg = OAuthSettings.from_env()
    assert cfg.configured() is True


def test_get_broker_http_sandbox_gate(monkeypatch, tmp_path):
    from opinion_trading.integrations.broker_adapter import get_broker_adapter

    monkeypatch.delenv("ENABLE_HTTP_BROKER_SANDBOX", raising=False)
    monkeypatch.delenv("BROKER_SANDBOX_URL", raising=False)
    a = get_broker_adapter("http_sandbox", str(tmp_path))
    assert a.__class__.__name__ == "SandboxBrokerAdapter"
    monkeypatch.setenv("ENABLE_HTTP_BROKER_SANDBOX", "1")
    b = get_broker_adapter("http_sandbox", str(tmp_path))
    assert b.__class__.__name__ == "HttpSandboxBrokerAdapter"
