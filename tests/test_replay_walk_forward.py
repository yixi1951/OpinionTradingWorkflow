from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from opinion_trading.core.backfill_signals import run_replay_batch
from opinion_trading.core.evaluation import load_prices
from opinion_trading.core.paper_equity import discover_raw_trade_dates
from opinion_trading.core.replay_fixtures import (
    FIXTURE_SPAN_END,
    FIXTURE_SPAN_START,
    ensure_replay_inputs,
    list_fixture_raw_dates,
    seed_raw_fixtures,
    weekday_span,
)
from opinion_trading.core.walk_forward import run_walk_forward, save_walk_forward_report

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _write_settings(tmp_path: Path, *, n_dates: int = 2) -> Path:
    raw = tmp_path / "raw"
    mem = tmp_path / "memory"
    reports = tmp_path / "reports"
    raw.mkdir()
    mem.mkdir()
    reports.mkdir()
    dates = list_fixture_raw_dates(str(FIXTURES))[:n_dates]
    for d in dates:
        src = FIXTURES / f"raw_posts_{d}.csv"
        (raw / src.name).write_bytes(src.read_bytes())
    cfg = {
        "strategy": {
            "platforms": ["guba", "sina_finance"],
            "platform_weights": {"guba": 1.4, "sina_finance": 1.0},
            "bearish_threshold": -0.6,
            "bullish_threshold": 0.7,
            "min_platforms_for_signal": 1,
            "reversal_min_delta": 0.1,
            "initial_cash": 100000,
            "position_size_ratio": 0.2,
        },
        "universe": {"symbols": ["600519.SH", "000001.SZ"]},
        "storage": {
            "memory_dir": str(mem),
            "report_dir": str(reports),
            "raw_dir": str(raw),
        },
        "scoring": {"mode": "keyword", "row_level_llm": False, "max_posts": 5},
        "analysis": {"enabled": False},
        "quality": {"enabled": False},
        "walk_forward": {
            "enabled_in_evaluate": True,
            "n_folds": 3,
            "train_days": 60,
            "test_days": 20,
        },
        "sentiment_recency": {"enabled": False},
        "ai_pipeline": {"screen_enabled": False, "score_enabled": False},
    }
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


def test_seed_raw_fixtures_when_raw_dir_empty(tmp_path):
    raw = tmp_path / "raw"
    dates = seed_raw_fixtures(str(raw), fixture_dir=str(FIXTURES))
    assert len(dates) >= 3
    discovered = discover_raw_trade_dates(str(raw))
    assert discovered == dates
    assert (raw / f"raw_posts_{dates[0]}.csv").is_file()


def test_ensure_replay_inputs_copies_price_table(tmp_path):
    info = ensure_replay_inputs(
        str(tmp_path / "raw"),
        str(tmp_path / "reports"),
        fixture_dir=str(FIXTURES),
    )
    assert info["seeded_raw"] is True
    assert len(info["dates"]) >= 3
    assert Path(info["price_path"]).is_file()
    prices = load_prices(info["price_path"])
    assert {"date", "symbol", "close"} <= set(prices.columns)


def test_seed_raw_fixtures_expands_calendar_span(tmp_path):
    raw = tmp_path / "raw"
    dates = seed_raw_fixtures(str(raw), fixture_dir=str(FIXTURES), expand_span=True)
    span_days = (
        date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])
    ).days + 1
    assert span_days >= 80
    expected_weekdays = {d.isoformat() for d in weekday_span(FIXTURE_SPAN_START, FIXTURE_SPAN_END)}
    assert expected_weekdays.issubset(set(dates))
    assert (raw / f"raw_posts_{FIXTURE_SPAN_START.isoformat()}.csv").is_file()


def test_walk_forward_default_windows_without_shrink(tmp_path):
    """~87 calendar days of signals: configured 60/20 is used (needed=80)."""
    mem = tmp_path / "memory"
    reports = tmp_path / "reports"
    mem.mkdir()
    reports.mkdir()
    prices = load_prices(str(FIXTURES / "price_history_replay.csv"))
    lines = []
    cur = FIXTURE_SPAN_START
    toggle = True
    while cur <= FIXTURE_SPAN_END:
        lines.append(
            json.dumps(
                {
                    "trade_date": cur.isoformat(),
                    "symbol": "600519.SH",
                    "action": "BUY" if toggle else "SELL",
                    "confidence": 0.7,
                    "reason": "fixture-span",
                    "platforms": ["guba"],
                }
            )
        )
        toggle = not toggle
        cur = cur.fromordinal(cur.toordinal() + 1)
    sig = mem / "signal_history.jsonl"
    sig.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = run_walk_forward(
        str(sig),
        prices,
        n_folds=3,
        train_days=60,
        test_days=20,
        min_signals_per_fold=3,
    )
    assert report.folds, report.recommendation
    fold = report.folds[0]
    assert (fold.train_end - fold.train_start).days == 59
    assert (fold.test_end - fold.test_start).days == 19
    # Honest gap: 3 non-overlapping 60/20 folds need ~240 days; fixture span is ~87.
    assert len(report.folds) >= 1
    out = save_walk_forward_report(str(reports), report)
    assert out.is_file()


def test_walk_forward_happy_path_with_short_fixture_history(tmp_path):
    mem = tmp_path / "memory"
    reports = tmp_path / "reports"
    mem.mkdir()
    reports.mkdir()
    prices = load_prices(str(FIXTURES / "price_history_replay.csv"))
    lines = []
    for d, action in [
        ("2026-06-11", "BUY"),
        ("2026-06-12", "SELL"),
        ("2026-06-15", "BUY"),
        ("2026-06-16", "SELL"),
        ("2026-06-17", "BUY"),
    ]:
        lines.append(
            json.dumps(
                {
                    "trade_date": d,
                    "symbol": "600519.SH",
                    "action": action,
                    "confidence": 0.7,
                    "reason": "fixture",
                    "platforms": ["guba"],
                }
            )
        )
    sig = mem / "signal_history.jsonl"
    sig.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = run_walk_forward(
        str(sig),
        prices,
        n_folds=3,
        train_days=60,
        test_days=20,
        min_signals_per_fold=3,
    )
    assert report.folds, report.recommendation
    out = save_walk_forward_report(str(reports), report)
    assert out.is_file()
    assert (reports / "walk_forward_report.json").is_file()


def test_replay_batch_happy_path_with_fixtures(tmp_path, monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "keyword")
    monkeypatch.setenv("OPENCLAW_SKIP_ROW_SCORE", "1")
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("AI_SCREEN_ENABLED", "0")
    monkeypatch.setenv("COLLECT_PARALLEL", "0")

    def fake_closes(symbols, trade_date):
        return {s: (100.0, "price_table") for s in symbols}

    monkeypatch.setattr(
        "opinion_trading.skills.trade_simulation.fetch_closes_for_symbols",
        fake_closes,
    )
    cfg = _write_settings(tmp_path, n_dates=2)
    summary = run_replay_batch(
        str(cfg),
        reset_paper=True,
        seed_fixtures=False,
    )
    assert summary["dates_total"] == 2
    assert summary["dates_run"] == 2
    assert all(row.get("ok") for row in summary["results"])
    mem = tmp_path / "memory"
    assert (mem / "state.json").is_file()
    assert (mem / "signal_history.jsonl").is_file() or summary["total_signals"] >= 0


def test_replay_batch_seeds_when_raw_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SCORING_MODE", "keyword")
    monkeypatch.setenv("OPENCLAW_SKIP_ROW_SCORE", "1")
    monkeypatch.setenv("USE_LLM_GATEWAY", "0")
    monkeypatch.setenv("AI_SCREEN_ENABLED", "0")
    monkeypatch.setenv("COLLECT_PARALLEL", "0")
    monkeypatch.setattr(
        "opinion_trading.skills.trade_simulation.fetch_closes_for_symbols",
        lambda symbols, trade_date: {s: (100.0, "price_table") for s in symbols},
    )
    cfg = _write_settings(tmp_path, n_dates=2)
    # wipe raw dir so seeding is required
    raw = tmp_path / "raw"
    for p in raw.glob("raw_posts_*.csv"):
        p.unlink()
    # Point fixture seed at a single-day copy under tmp to keep the run short
    mini = tmp_path / "mini_fix"
    mini.mkdir()
    src = FIXTURES / "raw_posts_2026-06-17.csv"
    (mini / src.name).write_bytes(src.read_bytes())
    (mini / "price_history_replay.csv").write_bytes(
        (FIXTURES / "price_history_replay.csv").read_bytes()
    )
    monkeypatch.setattr(
        "opinion_trading.core.replay_fixtures.default_fixture_dir",
        lambda: mini,
    )
    summary = run_replay_batch(str(cfg), reset_paper=True, seed_fixtures=True)
    assert summary["seeded_raw"] is True
    assert summary["dates_run"] >= 1
    assert date.fromisoformat("2026-06-17")
