from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from time import sleep
from typing import Dict

from opinion_trading.agents.roles import AnalystAgent, CollectorAgent, TraderAgent
from opinion_trading.core.config_loader import load_runtime_config
from opinion_trading.core.alert_notifier import AlertNotifier
from opinion_trading.core.memory_store import JsonLineMemoryStore
from opinion_trading.core.quality_report import QualityReportBuilder
from opinion_trading.core.raw_store import RawPostCsvStore
from opinion_trading.core.report_builder import DailyReportBuilder
from opinion_trading.core.daily_aggregator import build_daily_summary
from opinion_trading.integrations.platform_sentiment_real import (
    RealPlatformSentimentProvider,
)
from opinion_trading.skills.sentiment_analysis import SentimentAnalysisSkill
from opinion_trading.skills.sentiment_collection import SentimentCollectionSkill
from opinion_trading.skills.trade_simulation import PaperTradingSkill


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
        self.analyst = AnalystAgent(analyst_skill)
        self.trader = TraderAgent(trader_skill)

    def run_daily(self, run_date: date) -> Dict:
        raw_rows = []
        for symbol in self.config.symbols:
            for platform in self.config.strategy.platforms:
                raw_rows.extend(
                    self.provider.collect_raw_posts(
                        platform=platform,
                        symbol=symbol,
                        trade_date=run_date,
                    )
                )

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

        # build daily collection summary (CSV + MD)
        daily_summary_outputs = build_daily_summary(
            run_date.isoformat(), raw_rows, self.config.report_dir
        )

        snapshots = self.collector.run(
            symbols=self.config.symbols,
            platforms=self.config.strategy.platforms,
            trade_date=run_date,
        )
        self.store.append_many(
            "sentiment_history.jsonl", [x.to_dict() for x in snapshots]
        )

        signals, aggregated, best_combo, combo_scores = self.analyst.run(
            trade_date=run_date,
            snapshots=snapshots,
            platforms=self.config.strategy.platforms,
        )
        self.store.append_many("signal_history.jsonl", [x.to_dict() for x in signals])

        state = self.store.load_state()
        today_aggregated = aggregated.get(run_date, {})
        trades, updated_state = self.trader.run(
            trade_date=run_date,
            signals=signals,
            today_aggregated=today_aggregated,
            state=state,
        )

        self.store.append_many("trade_history.jsonl", [x.to_dict() for x in trades])
        self.store.save_state(updated_state)

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
        cycle_results = []
        latest_picks = []
        latest_combo = []
        previous_scores: Dict[str, float] = {}
        alerts: list[Dict] = []

        for i in range(iterations):
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
