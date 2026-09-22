"""Dashboard API: clean comment/sentiment evidence and spam filtering."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from opinion_trading.core.noise_filter import classify_noise, is_spam_or_ad
from opinion_trading.services.api_ui_data import (
    comments_for_symbol,
    load_dashboard_raw_posts,
    sentiment_evidence_posts,
)


def test_spam_markers_broker_soft_ads():
    assert is_spam_or_ad("证券开户即送88元红包，扫码进群领取")
    assert is_spam_or_ad("老师微信带单，私信领取涨停密码")
    noisy, reason = classify_noise("开户福利限时领，加微信跟单")
    assert noisy and reason == "spam_ad"


def _write_raw_partition(raw_root: Path, trade_date: str, symbol: str, rows: list) -> None:
    by = raw_root / "by_source"
    by.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(by / f"raw_posts_{trade_date}_guba.csv", index=False)
    df.to_csv(raw_root / f"raw_posts_{trade_date}.csv", index=False)


@pytest.fixture
def raw_fixture_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    d0 = (date.today() - timedelta(days=3)).isoformat()
    d1 = (date.today() - timedelta(days=2)).isoformat()
    d2 = (date.today() - timedelta(days=1)).isoformat()
    clean = {
        "trade_date": d0,
        "symbol": "600519.SH",
        "platform": "guba",
        "title": "茅台业绩超预期，长期看好消费龙头",
        "summary": "",
        "content": "茅台业绩超预期，长期看好消费龙头",
        "capture_status": "success",
        "is_noise": False,
        "ai_score": 0.42,
        "url": "https://guba.eastmoney.com/news/600519,111.html",
    }
    ad = {
        **clean,
        "trade_date": d1,
        "title": "加微信免费荐股，扫码进群领福利",
        "content": "加微信免费荐股，扫码进群领福利",
        "ai_score": 0.9,
        "is_noise": False,
        "url": "https://guba.eastmoney.com/news/600519,222.html",
    }
    clean2 = {
        **clean,
        "trade_date": d2,
        "title": "短期震荡不改中长期逻辑，继续持有",
        "content": "短期震荡不改中长期逻辑，继续持有",
        "ai_score": -0.18,
        "url": "https://guba.eastmoney.com/news/600519,333.html",
    }
    _write_raw_partition(raw, d0, "600519.SH", [clean])
    _write_raw_partition(raw, d1, "600519.SH", [ad])
    _write_raw_partition(raw, d2, "600519.SH", [clean2])
    return raw


def test_load_dashboard_raw_drops_ads_by_default(raw_fixture_dir: Path, monkeypatch):
    monkeypatch.setenv("RAW_DIR", str(raw_fixture_dir))
    monkeypatch.setenv("UI_RAW_LOOKBACK_DAYS", "30")
    df, _ = load_dashboard_raw_posts(include_noise=False)
    titles = df["title"].astype(str).tolist()
    assert any("业绩超预期" in t for t in titles)
    assert not any("加微信" in t for t in titles)
    assert len(df) >= 2


def test_comments_api_clean_rows_and_volume(raw_fixture_dir: Path, monkeypatch):
    monkeypatch.setenv("RAW_DIR", str(raw_fixture_dir))
    monkeypatch.setenv("UI_RAW_LOOKBACK_DAYS", "30")
    payload = comments_for_symbol("600519.SH", top_n=10, lookback_days=30)
    assert payload["ok"] is True
    assert payload["count"] >= 2
    texts = " ".join(str(r.get("title", "")) for r in payload["rows"])
    assert "加微信" not in texts


def test_sentiment_evidence_multi_day(raw_fixture_dir: Path, monkeypatch):
    monkeypatch.setenv("RAW_DIR", str(raw_fixture_dir))
    posts = sentiment_evidence_posts("600519.SH", limit=20, lookback_days=30)
    assert len(posts) >= 2
    assert all("加微信" not in str(p.get("title", "")) for p in posts)


def test_comments_api_include_noise_debug(raw_fixture_dir: Path, monkeypatch):
    monkeypatch.setenv("RAW_DIR", str(raw_fixture_dir))
    payload = comments_for_symbol(
        "600519.SH", top_n=10, include_noise=True, lookback_days=30
    )
    texts = " ".join(str(r.get("title", "")) for r in payload["rows"])
    assert "加微信" in texts


def test_sentiment_history_includes_evidence(raw_fixture_dir: Path, monkeypatch, tmp_path: Path):
    memory = tmp_path / "memory"
    memory.mkdir()
    row = {
        "trade_date": date.today().isoformat(),
        "symbol": "600519.SH",
        "platform": "guba",
        "sentiment_score": 0.12,
    }
    (memory / "sentiment_history.jsonl").write_text(
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MEMORY_DIR", str(memory))
    monkeypatch.setenv("RAW_DIR", str(raw_fixture_dir))
    monkeypatch.setenv("UI_RAW_LOOKBACK_DAYS", "30")

    from opinion_trading.services import api_app

    client = TestClient(api_app.app)
    res = client.get(
        "/v1/sentiment/history",
        params={"symbol": "600519.SH", "evidence_limit": 20, "lookback_days": 30},
    ).json()
    assert res["count"] == 1
    assert res["evidence_count"] >= 2
    assert all("加微信" not in str(p.get("title", "")) for p in res["evidence_posts"])
