from datetime import date

import pytest

from opinion_trading.agents.analyst_base import AnalystOpinion
from opinion_trading.agents.consensus_engine import ConsensusEngine, ConsensusSignal
from opinion_trading.core.data_quality import evaluate_raw_quality
from opinion_trading.core.explainability import (
    build_consensus_explanation,
    build_sentiment_explanation,
    enrich_sentiment_trade_signals,
    sentiment_kelly_from_confidence,
)
from opinion_trading.core.models import AggregatedSentiment
from opinion_trading.skills.trade_simulation import PaperTradingSkill
from opinion_trading.integrations.broker_adapter import (
    PaperBrokerAdapter,
    trade_signals_to_intents,
)
from opinion_trading.core.models import TradeSignal


def test_quality_gate_lowers_multiplier_on_noise():
    rows = [
        {
            "platform": "guba",
            "title": "短",
            "content": "x",
            "post_time": "",
            "capture_status": "fallback",
            "failure_reason": "timeout",
        }
        for _ in range(10)
    ]
    gate = evaluate_raw_quality(rows, max_noise_rate=0.05)
    assert gate.sentiment_confidence_multiplier < 1.0
    assert gate.messages


def test_explainability_lists_analysts():
    cs = ConsensusSignal(
        symbol="600519.SH",
        trade_date=date(2026, 6, 1),
        consensus_score=0.35,
        consensus_direction="BUY",
        confidence=0.6,
        kelly_fraction=0.1,
        analyst_opinions={
            "sentiment": AnalystOpinion(
                symbol="600519.SH",
                trade_date=date(2026, 6, 1),
                analyst_name="sentiment",
                score=0.4,
                confidence=0.7,
                reasoning="平台加权偏多",
            ),
            "technical": AnalystOpinion(
                symbol="600519.SH",
                trade_date=date(2026, 6, 1),
                analyst_name="technical",
                score=0.2,
                confidence=0.5,
                reasoning="RSI 中性偏多",
            ),
        },
        n_analysts=2,
        n_agreeing=2,
    )
    text = build_consensus_explanation(
        cs, analyst_weights={"sentiment": 0.4, "technical": 0.35}
    )
    assert "sentiment" in text
    assert "Kelly" in text or "kelly" in text.lower() or "仓位" in text


def test_broker_adapter_dry_run(tmp_path):
    sig = TradeSignal(
        trade_date=date(2026, 6, 1),
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        reason="test",
        platforms=["sentiment"],
        kelly_fraction=0.15,
    )
    intents = trade_signals_to_intents([sig], dry_run=True)
    out = PaperBrokerAdapter(str(tmp_path)).submit_intents(intents)
    assert out["count"] == 1
    assert out["dry_run"] is True


def test_consensus_engine_still_fuses_three_weights():
    engine = ConsensusEngine()
    ops = [
        AnalystOpinion("600519.SH", date(2026, 1, 1), "sentiment", 0.5, 0.8, "s"),
        AnalystOpinion("600519.SH", date(2026, 1, 1), "technical", 0.3, 0.7, "t"),
        AnalystOpinion("600519.SH", date(2026, 1, 1), "fundamental", 0.1, 0.6, "f"),
    ]
    signals = engine.compute_consensus(ops, date(2026, 1, 1))
    assert len(signals) == 1


def test_sentiment_explanation_and_kelly():
    agg = AggregatedSentiment(
        trade_date=date(2026, 6, 1),
        symbol="600519.SH",
        platform_scores={"guba": 0.5},
        platform_weights={"guba": 1.4},
    )
    k = sentiment_kelly_from_confidence(0.8, max_kelly_fraction=0.25)
    assert 0 < k <= 0.25
    text = build_sentiment_explanation(
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        trigger_platforms=["guba"],
        agg=agg,
        platform_weights={"guba": 1.4},
        bullish_threshold=0.7,
        bearish_threshold=-0.6,
        kelly_fraction=k,
        legacy_reason="Pessimism resonance reversal",
    )
    assert "纯情绪" in text
    assert "Kelly" in text
    assert "guba" in text


def test_enrich_sentiment_trade_signals():
    td = date(2026, 6, 1)
    agg = AggregatedSentiment(
        trade_date=td,
        symbol="600519.SH",
        platform_scores={"guba": -0.7},
        platform_weights={"guba": 1.0},
    )
    sig = TradeSignal(
        trade_date=td,
        symbol="600519.SH",
        action="BUY",
        confidence=0.7,
        reason="Pessimism resonance reversal",
        platforms=["guba"],
    )
    enrich_sentiment_trade_signals(
        [sig],
        aggregated_today={"600519.SH": agg},
        platform_weights={"guba": 1.0},
        bullish_threshold=0.7,
        bearish_threshold=-0.6,
    )
    assert sig.kelly_fraction is not None and sig.kelly_fraction > 0
    assert sig.explanation and "[纯情绪]" in sig.explanation


def test_settings_patch_explanation_lang(tmp_path):
    from opinion_trading.core.settings_patch import update_explanation_lang

    cfg = tmp_path / "settings.yaml"
    cfg.write_text("project:\n  name: x\n", encoding="utf-8")
    update_explanation_lang(str(cfg), "en")
    assert "explanation_lang: en" in cfg.read_text(encoding="utf-8")


def test_export_walk_forward_folds_csv(tmp_path):
    from opinion_trading.core.walk_forward_cache import (
        export_walk_forward_folds_csv,
        save_walk_forward_json,
    )
    from opinion_trading.core.walk_forward import WalkForwardFold, WalkForwardReport
    from opinion_trading.core.evaluation import EvalSummary

    rep_dir = str(tmp_path / "reports")
    fold = WalkForwardFold(
        train_start=date(2026, 1, 1),
        train_end=date(2026, 2, 1),
        test_start=date(2026, 2, 2),
        test_end=date(2026, 3, 1),
        train_summary=EvalSummary(10, 0.6, 0.01, 0.5, 0.2),
        test_summary=EvalSummary(5, 0.55, 0.008, 0.48, 0.15),
        degradation_accuracy=0.05,
        degradation_sharpe=0.05,
    )
    report = WalkForwardReport(
        folds=[fold],
        avg_test_accuracy=0.55,
        avg_test_sharpe=0.15,
        avg_degradation_accuracy=0.05,
        recommendation="ok",
    )
    save_walk_forward_json(rep_dir, report)
    blob = export_walk_forward_folds_csv(rep_dir)
    assert b"train_accuracy" in blob
    assert b"0.55" in blob or b"0.5500" in blob


def test_compute_raw_capture_rates():
    import pandas as pd
    from opinion_trading.ui_helpers import compute_raw_capture_rates

    df = pd.DataFrame(
        {
            "capture_status": ["success", "fallback", "stub"],
            "is_noise": [False, True, False],
        }
    )
    r = compute_raw_capture_rates(df)
    assert r["total_rows"] == 3
    assert r["fallback_rate"] == pytest.approx(2 / 3, rel=0.01)


def test_walk_forward_json_roundtrip(tmp_path):
    from opinion_trading.core.evaluation import EvalSummary
    from opinion_trading.core.walk_forward import WalkForwardFold, WalkForwardReport
    from opinion_trading.core.walk_forward_cache import (
        load_walk_forward_json,
        save_walk_forward_json,
    )

    es = EvalSummary(5, 0.6, 0.01, 0.5, 0.2)
    fold = WalkForwardFold(
        train_start=date(2026, 1, 1),
        train_end=date(2026, 2, 1),
        test_start=date(2026, 2, 2),
        test_end=date(2026, 2, 20),
        train_summary=es,
        test_summary=EvalSummary(3, 0.5, 0.0, 0.4, 0.1),
        degradation_accuracy=0.1,
        degradation_sharpe=0.05,
    )
    report = WalkForwardReport(
        folds=[fold],
        avg_test_accuracy=0.5,
        avg_test_sharpe=0.1,
        avg_degradation_accuracy=0.1,
        recommendation="ok",
    )
    rep_dir = str(tmp_path / "reports")
    save_walk_forward_json(rep_dir, report)
    loaded = load_walk_forward_json(rep_dir)
    assert loaded and len(loaded["folds"]) == 1


def test_env_bootstrap_loads(tmp_path, monkeypatch):
    from opinion_trading.core.env_bootstrap import load_dotenv_if_present

    monkeypatch.delenv("COLLECT_PARALLEL", raising=False)
    (tmp_path / ".env").write_text("COLLECT_PARALLEL=0\n", encoding="utf-8")
    load_dotenv_if_present(tmp_path)
    import os

    assert os.environ.get("COLLECT_PARALLEL") == "0"


def test_discover_raw_trade_dates(tmp_path):
    from opinion_trading.core.paper_equity import discover_raw_trade_dates

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "raw_posts_2026-06-17.csv").write_text("x", encoding="utf-8")
    (raw / "raw_posts_2026-06-03.csv").write_text("x", encoding="utf-8")
    dates = discover_raw_trade_dates(str(raw))
    assert dates == ["2026-06-03", "2026-06-17"]


def test_paper_equity_curve_from_trades(tmp_path):
    from opinion_trading.core.paper_equity import build_paper_equity_curve

    mem = tmp_path / "memory"
    mem.mkdir()
    line = (
        '{"trade_date":"2026-06-17","symbol":"600519.SH","action":"BUY",'
        '"shares":10,"price":100.0,"cash_after":99000.0,"note":""}\n'
    )
    (mem / "trade_history.jsonl").write_text(line, encoding="utf-8")
    df = build_paper_equity_curve(str(mem), use_market_prices=False)
    assert len(df) == 1
    assert float(df.iloc[0]["cash"]) == 99000.0


def test_quality_gate_history_append(tmp_path):
    from opinion_trading.core.data_quality import QualityGateResult
    from opinion_trading.core.quality_gate_history import (
        append_quality_gate_record,
        load_quality_gate_history,
    )

    mem = tmp_path / "memory"
    gate = QualityGateResult(
        overall_pass=True,
        platform_pass={"guba": True},
        noise_rate=0.1,
        fallback_rate=0.2,
        sentiment_confidence_multiplier=0.9,
        block_new_signals=False,
        messages=[],
    )
    append_quality_gate_record(str(mem), "2026-06-17", gate, raw_row_count=10)
    rows = load_quality_gate_history(str(mem))
    assert len(rows) == 1
    assert rows[0]["fallback_rate"] == 0.2


def test_set_analysis_enabled(tmp_path):
    from opinion_trading.core.settings_patch import set_analysis_enabled

    cfg = tmp_path / "settings.yaml"
    cfg.write_text("analysis:\n  enabled: true\n", encoding="utf-8")
    set_analysis_enabled(str(cfg), False)
    assert "enabled: false" in cfg.read_text(encoding="utf-8").lower()


def test_settings_patch_universe(tmp_path):
    from opinion_trading.core.settings_patch import (
        parse_symbol_list,
        update_universe_symbols,
    )

    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        "universe:\n  symbols:\n  - 600519.SH\n",
        encoding="utf-8",
    )
    update_universe_symbols(str(cfg), ["000001.SZ", "601318.SH"])
    text = cfg.read_text(encoding="utf-8")
    assert "000001.SZ" in text
    assert parse_symbol_list("600519.SH\n# comment\n") == ["600519.SH"]


def test_sentiment_explanation_english():
    from opinion_trading.core.explainability import build_sentiment_explanation

    txt = build_sentiment_explanation(
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        trigger_platforms=["guba"],
        agg=None,
        platform_weights={"guba": 1.0},
        bullish_threshold=0.7,
        bearish_threshold=-0.6,
        lang="en",
    )
    assert "[Sentiment-only]" in txt


def test_recency_weight_decays():
    from datetime import datetime, timedelta

    from opinion_trading.core.time_decay import recency_weight, weighted_mean_scores

    now = datetime(2026, 6, 17, 12, 0, 0)
    old = now - timedelta(hours=24)
    assert recency_weight(old, as_of=now, half_life_hours=24.0) == pytest.approx(
        0.5, rel=0.05
    )
    rows = [
        {"post_time": "2026-06-17 11:00:00", "ai_score": 1.0},
        {"post_time": "2026-06-16 11:00:00", "ai_score": -1.0},
    ]
    m = weighted_mean_scores(rows, date(2026, 6, 17), half_life_hours=24.0)
    assert m > 0


def test_export_zip_nonempty(tmp_path):
    from opinion_trading.core.export_bundle import build_dashboard_export_zip

    rep = tmp_path / "reports"
    mem = tmp_path / "memory"
    rep.mkdir()
    mem.mkdir()
    (mem / "state.json").write_text("{}", encoding="utf-8")
    data = build_dashboard_export_zip(str(rep), str(mem))
    assert len(data) > 100


def test_text_dedup_removes_duplicates():
    from opinion_trading.core.text_dedup import dedupe_raw_rows

    rows = [
        {"platform": "guba", "symbol": "600519.SH", "title": "A", "content": "same"},
        {"platform": "guba", "symbol": "600519.SH", "title": "A", "content": "same"},
    ]
    out, n = dedupe_raw_rows(rows)
    assert len(out) == 1
    assert n == 1


def test_eval_summary_extended_metrics():
    from opinion_trading.core.evaluation import EvalSummary

    s = EvalSummary(
        10,
        0.6,
        0.01,
        0.55,
        0.5,
        max_drawdown=-0.12,
        profit_factor=1.2,
        payoff_ratio=1.1,
    )
    assert s.max_drawdown == -0.12


def test_event_log_roundtrip(tmp_path):
    from opinion_trading.core.event_log import append_event, load_recent_events

    mem = str(tmp_path)
    append_event(mem, "signal_emitted", {"symbol": "600519.SH"}, trade_date="2026-06-01")
    rows = load_recent_events(mem, limit=5)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "signal_emitted"


def test_risk_rejects_oversized_kelly():
    from opinion_trading.core.risk_controls import RiskLimits, apply_risk_to_signals

    sig = TradeSignal(
        trade_date=date(2026, 6, 1),
        symbol="600519.SH",
        action="BUY",
        confidence=0.9,
        reason="x",
        platforms=["guba"],
        kelly_fraction=0.9,
    )
    out = apply_risk_to_signals(
        [sig],
        portfolio_value=100_000,
        cash=100_000,
        positions={},
        limits=RiskLimits(max_single_symbol_notional_pct=0.25),
    )
    assert len(out.rejected) == 1


def test_paper_trading_uses_kelly_budget(monkeypatch):
    td = date(2026, 6, 1)

    def fake_closes(symbols, trade_date):
        return {s: (100.0, "market") for s in symbols}

    monkeypatch.setattr(
        "opinion_trading.skills.trade_simulation.fetch_closes_for_symbols",
        fake_closes,
    )
    skill = PaperTradingSkill(100_000, position_size_ratio=0.2, use_market_prices=True)
    sig = TradeSignal(
        trade_date=td,
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        reason="x",
        platforms=["guba"],
        kelly_fraction=0.1,
    )
    agg = AggregatedSentiment(
        trade_date=td, symbol="600519.SH", platform_scores={"guba": 0.1}
    )
    trades, state = skill.simulate(
        td, [sig], {"600519.SH": agg}, {"cash": 100_000, "positions": {}}
    )
    assert len(trades) == 1
    assert trades[0].shares == 100  # 10% of 100k @ 100
    val = skill.portfolio_value({"600519.SH": agg}, state)
    assert val == pytest.approx(100_000, rel=0.01)
