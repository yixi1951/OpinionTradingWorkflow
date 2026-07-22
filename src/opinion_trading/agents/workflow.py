from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional

from opinion_trading.core.log_utils import get_logger
from opinion_trading.agents.roles import (
    CollectorAgent,
    MultiAnalystAgent,
    SentimentAnalystAgent,
    TraderAgent,
)
from opinion_trading.core.config_loader import load_runtime_config
from opinion_trading.core.alert_notifier import AlertNotifier
from opinion_trading.core.memory_store import JsonLineMemoryStore
from opinion_trading.core.quality_report import QualityReportBuilder
from opinion_trading.core.raw_store import RawPostCsvStore
from opinion_trading.core.report_builder import DailyReportBuilder
from opinion_trading.core.daily_aggregator import build_daily_summary
from opinion_trading.core.data_quality import evaluate_raw_quality
from opinion_trading.integrations.broker_adapter import (
    PaperBrokerAdapter,
    SignalExportAdapter,
    get_broker_adapter,
    trade_signals_to_intents,
)
from opinion_trading.integrations.platform_sentiment_real import (
    RealPlatformSentimentProvider,
)
from opinion_trading.skills.sentiment_analysis import SentimentAnalysisSkill
from opinion_trading.skills.sentiment_collection import SentimentCollectionSkill
from opinion_trading.skills.trade_simulation import PaperTradingSkill

logger = get_logger(__name__)


class OpinionTradingWorkflow:
    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        self.config = load_runtime_config(config_path)
        self.store = JsonLineMemoryStore(self.config.memory_dir)
        self.reporter = DailyReportBuilder(self.config.report_dir)
        self.raw_store = RawPostCsvStore(self.config.raw_dir)
        self.quality_reporter = QualityReportBuilder(self.config.report_dir)
        self.provider = RealPlatformSentimentProvider()
        self.alert_notifier = AlertNotifier()

        collector_skill = SentimentCollectionSkill(self.provider)
        analyst_skill = SentimentAnalysisSkill(
            bearish_threshold=self.config.strategy.bearish_threshold,
            bullish_threshold=self.config.strategy.bullish_threshold,
            min_platforms_for_signal=self.config.strategy.min_platforms_for_signal,
            reversal_min_delta=self.config.strategy.reversal_min_delta,
            platform_weights=self.config.strategy.platform_weights,
        )
        trader_skill = PaperTradingSkill(
            initial_cash=self.config.strategy.initial_cash,
            position_size_ratio=self.config.strategy.position_size_ratio,
        )

        self.collector = CollectorAgent(collector_skill)
        # Use MultiAnalystAgent if analysis config is enabled, else fallback
        if self.config.analysis and self.config.analysis.enabled:
            self.analyst = MultiAnalystAgent(
                sentiment_analyst=SentimentAnalystAgent(analyst_skill),
                analysis_cfg=self.config.analysis,
                explanation_lang=getattr(self.config, "explanation_lang", "zh"),
            )
            logger.info("Multi-agent analysis ENABLED (sentiment + technical + fundamental)")
        else:
            self.analyst = SentimentAnalystAgent(analyst_skill)
            logger.info("Multi-agent analysis DISABLED (pure sentiment only)")
        self.trader = TraderAgent(trader_skill)

    def run_daily(self, run_date: date, *, skip_crawl: bool = False) -> Dict:
        logger.info(
            "run_daily started — %d symbols, %d platforms skip_crawl=%s",
            len(self.config.symbols),
            len(self.config.strategy.platforms),
            skip_crawl,
        )
        raw_rows: List[Dict] = []
        if skip_crawl:
            raw_rows = self.raw_store.load_rows_for_date(run_date.isoformat())
            if not raw_rows:
                raise FileNotFoundError(
                    f"No cached raw CSV for {run_date.isoformat()}; "
                    f"run daily without --fast-daily first."
                )
            logger.info("Fast daily: loaded %d rows from cache", len(raw_rows))
        else:
            import os

            from opinion_trading.core.parallel_collect import collect_raw_posts_parallel

            parallel = os.environ.get("COLLECT_PARALLEL", "1").lower() not in (
                "0",
                "false",
                "no",
            )
            if parallel and len(self.config.symbols) * len(self.config.strategy.platforms) > 1:
                prog_log = str(
                    Path(self.config.report_dir)
                    / f"collect_progress_{run_date.isoformat()}.jsonl"
                )
                raw_rows = collect_raw_posts_parallel(
                    self.provider,
                    self.config.symbols,
                    self.config.strategy.platforms,
                    run_date,
                    progress_log_path=prog_log,
                )
            else:
                total_combos = len(self.config.symbols) * len(
                    self.config.strategy.platforms
                )
                for idx, symbol in enumerate(self.config.symbols):
                    for platform in self.config.strategy.platforms:
                        logger.debug(
                            "Collecting [%d/%d] %s/%s",
                            idx * len(self.config.strategy.platforms)
                            + self.config.strategy.platforms.index(platform)
                            + 1,
                            total_combos,
                            platform,
                            symbol,
                        )
                        raw_rows.extend(
                            self.provider.collect_raw_posts(
                                platform=platform,
                                symbol=symbol,
                                trade_date=run_date,
                            )
                        )

        from opinion_trading.core.text_dedup import dedupe_raw_rows

        raw_rows, dup_removed = dedupe_raw_rows(raw_rows)
        if dup_removed:
            logger.info("Dedup removed %d duplicate raw rows", dup_removed)

        from opinion_trading.core.noise_filter import filter_noisy_rows
        from opinion_trading.core.semantic_enrichment import enrich_raw_rows

        raw_rows, noise_stats = filter_noisy_rows(raw_rows, mark_only=True)
        raw_rows = enrich_raw_rows(raw_rows)
        logger.info(
            "Collected %d raw rows (noise_rate=%.1f%%, semantic enrichment applied)",
            len(raw_rows),
            100.0 * float(noise_stats.get("noise_rate", 0.0)),
        )

        from opinion_trading.core.quality_monitor import (
            evaluate_quality_monitor,
            persist_and_alert,
        )

        qmon = evaluate_quality_monitor(raw_rows, trade_date=run_date.isoformat())
        persist_and_alert(qmon, report_dir=self.config.report_dir, notify=not qmon.ok)
        if qmon.alerts:
            logger.warning("Quality monitor alerts: %s", "; ".join(qmon.alerts))

        # Optional structured / document persistence
        try:
            from opinion_trading.core.storage import get_storage

            store = get_storage()
            structured = [
                {
                    "trade_date": r.get("trade_date"),
                    "symbol": r.get("symbol"),
                    "platform": r.get("platform"),
                    "ai_score": r.get("ai_score"),
                    "keyword_score": r.get("keyword_score"),
                    "event_type": r.get("event_type"),
                    "authority_weight": r.get("authority_weight"),
                    "entity_matched": r.get("entity_matched"),
                }
                for r in raw_rows
            ]
            store.save_structured("sentiment_scores", structured)
            store.save_documents("raw_posts", raw_rows)
        except Exception as exc:
            logger.debug("Optional storage backend skipped: %s", exc)

        raw_outputs = self.raw_store.save_partitioned_rows(
            run_date.isoformat(), raw_rows
        )
        failure_outputs = self.raw_store.save_failure_logs(
            run_date.isoformat(), raw_rows
        )
        raw_csv_path = raw_outputs["combined"]
        quality_report_path = self.quality_reporter.build(
            run_date.isoformat(), raw_rows, raw_csv_path
        )

        quality_gate = None
        qcfg = self.config.quality
        if qcfg and qcfg.enabled:
            quality_gate = evaluate_raw_quality(
                raw_rows,
                max_fallback_rate=qcfg.max_fallback_rate,
                max_noise_rate=qcfg.max_noise_rate,
                fail_multiplier=qcfg.fail_confidence_multiplier,
            )
            if quality_gate.messages:
                logger.warning(
                    "Data quality gate: %s",
                    "; ".join(quality_gate.messages),
                )
            if qcfg.block_signals_on_severe_failure and not quality_gate.overall_pass:
                quality_gate.block_new_signals = True
            from opinion_trading.core.quality_gate_history import (
                append_quality_gate_record,
            )

            append_quality_gate_record(
                self.config.memory_dir,
                run_date.isoformat(),
                quality_gate,
                raw_row_count=len(raw_rows),
            )

        # build daily collection summary (CSV + MD)
        daily_summary_outputs = build_daily_summary(
            run_date.isoformat(), raw_rows, self.config.report_dir
        )

        rec = getattr(self.config, "sentiment_recency", None)
        rec_on = bool(rec and rec.enabled)
        half_life = float(rec.half_life_hours) if rec else 24.0
        from opinion_trading.core.snapshot_from_raw import snapshots_from_raw_rows

        if skip_crawl or rec_on:
            snapshots = snapshots_from_raw_rows(
                raw_rows,
                run_date,
                recency_enabled=rec_on,
                half_life_hours=half_life,
            )
            if not snapshots:
                snapshots = self.collector.run(
                    symbols=self.config.symbols,
                    platforms=self.config.strategy.platforms,
                    trade_date=run_date,
                )
        else:
            snapshots = self.collector.run(
                symbols=self.config.symbols,
                platforms=self.config.strategy.platforms,
                trade_date=run_date,
            )
        self.store.append_many(
            "sentiment_history.jsonl", [x.to_dict() for x in snapshots]
        )

        analyst_kwargs = {
            "trade_date": run_date,
            "snapshots": snapshots,
            "platforms": self.config.strategy.platforms,
        }
        if isinstance(self.analyst, MultiAnalystAgent):
            analyst_kwargs["quality_gate"] = quality_gate
        signals, aggregated, best_combo, combo_scores = self.analyst.run(
            **analyst_kwargs
        )
        if quality_gate and not isinstance(self.analyst, MultiAnalystAgent):
            from opinion_trading.core.data_quality import (
                apply_quality_to_sentiment_confidence,
            )

            if quality_gate.block_new_signals:
                from opinion_trading.core.event_log import append_event

                append_event(
                    self.config.memory_dir,
                    "signal_blocked",
                    {
                        "reason": "quality_gate",
                        "messages": quality_gate.messages,
                    },
                    trade_date=run_date.isoformat(),
                )
                signals = []
            else:
                for sig in signals:
                    sig.confidence = apply_quality_to_sentiment_confidence(
                        sig.confidence, quality_gate
                    )
        if not isinstance(self.analyst, MultiAnalystAgent) and signals:
            from opinion_trading.core.explainability import enrich_sentiment_trade_signals

            acfg = self.config.analysis
            max_k = acfg.max_kelly_fraction if acfg else 0.25
            strat = self.config.strategy
            enrich_sentiment_trade_signals(
                signals,
                aggregated_today=aggregated.get(run_date, {}),
                platform_weights=strat.platform_weights,
                bullish_threshold=strat.bullish_threshold,
                bearish_threshold=strat.bearish_threshold,
                max_kelly_fraction=max_k,
                lang=getattr(self.config, "explanation_lang", "zh"),
            )
        self.store.append_many("signal_history.jsonl", [x.to_dict() for x in signals])
        if signals:
            from opinion_trading.core.event_log import append_event

            for sig in signals:
                append_event(
                    self.config.memory_dir,
                    "signal_emitted",
                    {
                        "symbol": sig.symbol,
                        "action": sig.action,
                        "confidence": sig.confidence,
                        "kelly_fraction": sig.kelly_fraction,
                    },
                    trade_date=run_date.isoformat(),
                )

        state = self.store.load_state()
        today_aggregated = aggregated.get(run_date, {})
        ref_prices: Dict[str, float] = {}
        if signals:
            from opinion_trading.core.market_data import fetch_closes_for_symbols

            syms = sorted({s.symbol for s in signals})
            closes = fetch_closes_for_symbols(syms, run_date)
            for sym, (px, _src) in closes.items():
                if px is not None and px > 0:
                    ref_prices[sym] = float(px)

        execution_export: Dict[str, object] = {}
        ecfg = self.config.execution
        if ecfg and ecfg.export_intents and signals:
            kelly_map = {
                s.symbol: float(
                    s.kelly_fraction
                    if s.kelly_fraction is not None
                    else self.config.strategy.position_size_ratio
                )
                for s in signals
            }
            intents = trade_signals_to_intents(
                signals,
                position_size_ratio=self.config.strategy.position_size_ratio,
                kelly_by_symbol=kelly_map,
                dry_run=ecfg.dry_run,
            )
            mode = (ecfg.mode or "paper").lower()
            if mode == "simulation":
                from opinion_trading.integrations.simulation_broker import (
                    SimulationBrokerAdapter,
                )

                sim = SimulationBrokerAdapter(self.config.report_dir)
                execution_export["simulation"] = sim.match_intents(
                    intents,
                    prices=ref_prices,
                    slippage_bps=ecfg.simulation_slippage_bps,
                )
            broker = get_broker_adapter(ecfg.mode, self.config.report_dir)
            execution_export["primary"] = broker.submit_intents(intents)
            execution_export["jsonl"] = PaperBrokerAdapter(
                self.config.report_dir
            ).submit_intents(intents)
            execution_export["csv"] = SignalExportAdapter(
                self.config.report_dir
            ).submit_intents(intents)
            from opinion_trading.core.event_log import append_event

            for intent in intents:
                append_event(
                    self.config.memory_dir,
                    "execution_intent",
                    intent.to_dict(),
                    trade_date=run_date.isoformat(),
                )

        signals_for_trade = signals
        if signals:
            from opinion_trading.core.risk_controls import RiskLimits, apply_risk_to_signals

            rcfg = self.config.risk
            limits = RiskLimits(
                max_daily_loss_pct=rcfg.max_daily_loss_pct if rcfg else 0.05,
                max_single_symbol_notional_pct=(
                    rcfg.max_single_symbol_notional_pct if rcfg else 0.25
                ),
                max_open_positions=rcfg.max_open_positions if rcfg else 10,
            )
            cash = float(state.get("cash", self.config.strategy.initial_cash))
            positions = dict(state.get("positions", {}))
            pv = self.trader.skill.portfolio_value(today_aggregated, state)
            risk_out = apply_risk_to_signals(
                signals,
                portfolio_value=pv,
                cash=cash,
                positions=positions,
                limits=limits,
                reference_prices=ref_prices,
            )
            if risk_out.rejected:
                from opinion_trading.core.event_log import append_event

                for sig, reason in risk_out.rejected:
                    append_event(
                        self.config.memory_dir,
                        "risk_reject",
                        {
                            "symbol": sig.symbol,
                            "action": sig.action,
                            "reason": reason,
                        },
                        trade_date=run_date.isoformat(),
                    )
            signals_for_trade = risk_out.allowed

        trades, updated_state = self.trader.run(
            trade_date=run_date,
            signals=signals_for_trade,
            today_aggregated=today_aggregated,
            state=state,
        )

        self.store.append_many("trade_history.jsonl", [x.to_dict() for x in trades])
        if trades:
            from opinion_trading.core.event_log import append_event

            for tr in trades:
                append_event(
                    self.config.memory_dir,
                    "paper_fill",
                    tr.to_dict(),
                    trade_date=run_date.isoformat(),
                )
        self.store.save_state(updated_state)

        if quality_gate is not None:
            gate_record = {
                "trade_date": run_date.isoformat(),
                "overall_pass": quality_gate.overall_pass,
                "sentiment_confidence_multiplier": quality_gate.sentiment_confidence_multiplier,
                "block_new_signals": quality_gate.block_new_signals,
                "noise_rate": quality_gate.noise_rate,
                "fallback_rate": quality_gate.fallback_rate,
                "messages": quality_gate.messages,
            }
            self.store.append_many("quality_gate_history.jsonl", [gate_record])

        report_path = self.reporter.build(
            trade_date=run_date.isoformat(),
            best_platform_combo=best_combo,
            combo_scores=combo_scores,
            aggregated_today=today_aggregated,
            signals=signals,
            trades=trades,
            state=updated_state,
        )

        return {
            "run_time": datetime.now().isoformat(),
            "run_date": run_date.isoformat(),
            "signals": len(signals),
            "trades": len(trades),
            "report": str(report_path),
            "raw_csv": str(raw_csv_path),
            "raw_sources": {
                k: str(v) for k, v in raw_outputs.items() if k != "combined"
            },
            "failure_logs": {k: str(v) for k, v in failure_outputs.items()},
            "quality_report": str(quality_report_path),
            "daily_summary": str(daily_summary_outputs.get("csv")),
            "daily_summary_md": str(daily_summary_outputs.get("md")),
            "best_combo": best_combo,
            "state": updated_state,
            "quality_gate": {
                "overall_pass": quality_gate.overall_pass if quality_gate else True,
                "multiplier": (
                    quality_gate.sentiment_confidence_multiplier
                    if quality_gate
                    else 1.0
                ),
                "messages": quality_gate.messages if quality_gate else [],
            },
            "execution_export": execution_export,
        }

    def run_realtime(
        self,
        iterations: int = 3,
        interval_seconds: int = 60,
        top_n: int = 3,
        alert_threshold: float = 0.25,
        yellow_threshold: float = 0.20,
        orange_threshold: float = 0.35,
        red_threshold: float = 0.50,
    ) -> Dict:
        """Run real-time polling cycles and produce AI stock picks from live sentiment."""
        run_date = datetime.now().date()
        logger.info(
            "run_realtime started — %d iterations, %ds interval, %d symbols",
            iterations, interval_seconds, len(self.config.symbols),
        )
        cycle_results = []
        latest_picks = []
        latest_combo = []
        previous_scores: Dict[str, float] = {}
        alerts: list[Dict] = []

        rec_rt = getattr(self.config, "sentiment_recency", None)
        rec_rt_on = bool(rec_rt and rec_rt.enabled)
        half_rt = float(rec_rt.half_life_hours) if rec_rt else 24.0

        for i in range(iterations):
            logger.info("Realtime cycle %d/%d", i + 1, iterations)
            if rec_rt_on:
                from opinion_trading.core.snapshot_from_raw import (
                    snapshots_from_raw_rows,
                )
                from opinion_trading.core.text_dedup import dedupe_raw_rows

                rt_raw: List[Dict] = []
                for symbol in self.config.symbols:
                    for platform in self.config.strategy.platforms:
                        rt_raw.extend(
                            self.provider.collect_raw_posts(
                                platform=platform,
                                symbol=symbol,
                                trade_date=run_date,
                            )
                        )
                rt_raw, _ = dedupe_raw_rows(rt_raw)
                snapshots = snapshots_from_raw_rows(
                    rt_raw,
                    run_date,
                    recency_enabled=True,
                    half_life_hours=half_rt,
                )
                if not snapshots:
                    snapshots = self.collector.run(
                        symbols=self.config.symbols,
                        platforms=self.config.strategy.platforms,
                        trade_date=run_date,
                    )
            else:
                snapshots = self.collector.run(
                    symbols=self.config.symbols,
                    platforms=self.config.strategy.platforms,
                    trade_date=run_date,
                )
            self.store.append_many(
                "realtime_sentiment_history.jsonl", [x.to_dict() for x in snapshots]
            )

            signals, aggregated, best_combo, _ = self.analyst.run(
                trade_date=run_date,
                snapshots=snapshots,
                platforms=self.config.strategy.platforms,
            )
            latest_combo = best_combo
            self.store.append_many(
                "signal_history.jsonl", [x.to_dict() for x in signals]
            )

            today_aggregated = aggregated.get(run_date, {})

            effective_yellow = max(alert_threshold, yellow_threshold)

            for symbol, agg in today_aggregated.items():
                current_score = float(agg.average_score)
                prev = previous_scores.get(symbol)
                if prev is not None:
                    delta = current_score - prev
                    severity = self._classify_alert_severity(
                        delta=delta,
                        yellow_threshold=effective_yellow,
                        orange_threshold=orange_threshold,
                        red_threshold=red_threshold,
                    )
                    if severity is not None:
                        alert = {
                            "time": datetime.now().isoformat(),
                            "symbol": symbol,
                            "previous_score": prev,
                            "current_score": current_score,
                            "delta": delta,
                            "thresholds": {
                                "yellow": effective_yellow,
                                "orange": orange_threshold,
                                "red": red_threshold,
                            },
                            "severity": severity,
                            "direction": "UP" if delta > 0 else "DOWN",
                        }
                        push_result = self.alert_notifier.push_alert(alert)
                        alert["push_result"] = push_result
                        alerts.append(alert)
                        self.store.append_many("realtime_alerts.jsonl", [alert])
                previous_scores[symbol] = current_score

            ranked = sorted(
                [
                    {
                        "symbol": symbol,
                        "avg_score": agg.average_score,
                        "platform_scores": agg.platform_scores,
                    }
                    for symbol, agg in today_aggregated.items()
                ],
                key=lambda x: x["avg_score"],
                reverse=True,
            )
            latest_picks = ranked[: max(1, top_n)]
            pick_history = []
            for idx, row in enumerate(latest_picks, start=1):
                score = float(row.get("avg_score", 0.0))
                pick_history.append(
                    {
                        "trade_date": run_date.isoformat(),
                        "symbol": row.get("symbol", ""),
                        "score": score,
                        "action": "BUY" if score >= 0 else "SELL",
                        "confidence": abs(score),
                        "rank": idx,
                        "platform_scores": row.get("platform_scores", {}),
                    }
                )
            if pick_history:
                self.store.append_many("realtime_pick_history.jsonl", pick_history)

            cycle_results.append(
                {
                    "cycle": i + 1,
                    "time": datetime.now().isoformat(),
                    "signals": len(signals),
                    "best_combo": best_combo,
                    "top_pick": latest_picks[0]["symbol"] if latest_picks else "",
                    "top_score": latest_picks[0]["avg_score"] if latest_picks else 0.0,
                }
            )

            if i < iterations - 1:
                sleep(max(1, interval_seconds))

        report_paths = self._write_realtime_pick_report(
            latest_picks, latest_combo, cycle_results, alerts
        )
        return {
            "run_time": datetime.now().isoformat(),
            "mode": "realtime",
            "iterations": iterations,
            "interval_seconds": interval_seconds,
            "top_n": top_n,
            "alert_threshold": alert_threshold,
            "yellow_threshold": effective_yellow,
            "orange_threshold": orange_threshold,
            "red_threshold": red_threshold,
            "alerts": alerts,
            "best_combo": latest_combo,
            "picks": latest_picks,
            "report_csv": str(report_paths["csv"]),
            "report_md": str(report_paths["md"]),
            "alert_file": str(report_paths["alerts"]),
        }

    def _write_realtime_pick_report(
        self, picks, best_combo, cycle_results, alerts
    ) -> Dict[str, Path]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = Path(self.config.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)

        csv_path = report_dir / f"realtime_picks_{ts}.csv"
        md_path = report_dir / f"realtime_picks_{ts}.md"
        alert_path = report_dir / f"realtime_alerts_{ts}.jsonl"

        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["symbol", "avg_score", "platform_scores"]
            )
            writer.writeheader()
            for row in picks:
                writer.writerow(
                    {
                        "symbol": row.get("symbol", ""),
                        "avg_score": f"{float(row.get('avg_score', 0.0)):.4f}",
                        "platform_scores": ", ".join(
                            f"{k}:{v:.3f}"
                            for k, v in row.get("platform_scores", {}).items()
                        ),
                    }
                )

        md_lines = [
            f"# Realtime AI Picks - {datetime.now().isoformat()}",
            "",
            f"- Best platform combo: {', '.join(best_combo) if best_combo else 'N/A'}",
            "",
            "## Top Picks",
        ]
        if picks:
            for idx, row in enumerate(picks, start=1):
                md_lines.append(
                    f"- #{idx} {row.get('symbol', '')} | avg_score={float(row.get('avg_score', 0.0)):.4f} | "
                    + ", ".join(
                        f"{k}:{v:.3f}"
                        for k, v in row.get("platform_scores", {}).items()
                    )
                )
        else:
            md_lines.append("- No picks generated.")

        md_lines.append("")
        md_lines.append("## Cycles")
        for c in cycle_results:
            md_lines.append(
                f"- cycle={c['cycle']} | time={c['time']} | signals={c['signals']} | "
                f"top={c['top_pick']} ({float(c['top_score']):.4f})"
            )

        md_lines.append("")
        md_lines.append("## Score Alerts")
        if alerts:
            for a in alerts:
                md_lines.append(
                    f"- {a['time']} | {a['symbol']} | {a['severity']} {a['direction']} | delta={float(a['delta']):.4f} "
                    f"({float(a['previous_score']):.4f} -> {float(a['current_score']):.4f})"
                )
        else:
            md_lines.append("- No score-change alerts triggered.")

        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        with alert_path.open("w", encoding="utf-8") as f:
            for row in alerts:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        return {"csv": csv_path, "md": md_path, "alerts": alert_path}

    def _classify_alert_severity(
        self,
        *,
        delta: float,
        yellow_threshold: float,
        orange_threshold: float,
        red_threshold: float,
    ) -> str | None:
        value = abs(float(delta))
        if value >= red_threshold:
            return "RED"
        if value >= orange_threshold:
            return "ORANGE"
        if value >= yellow_threshold:
            return "YELLOW"
        return None
