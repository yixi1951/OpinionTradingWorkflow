from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd

from opinion_trading.core.env_bootstrap import load_dotenv_if_present
from opinion_trading.core.log_utils import configure_logging, get_logger

load_dotenv_if_present(Path(__file__).resolve().parents[2])
from opinion_trading.agents.workflow import OpinionTradingWorkflow  # noqa: E402
from opinion_trading.core.backtest import StrategyBacktester  # noqa: E402
from opinion_trading.core.evaluation import load_prices, load_signals  # noqa: E402
from opinion_trading.core.monthly_training import (  # noqa: E402
    build_monthly_training_frame,
    fetch_prices_with_timeout,
    load_training_history,
    save_monthly_training_report,
)
from opinion_trading.core.visualization import (  # noqa: E402
    load_backtest_csv,
    plot_sharpe_vs_threshold,
    top_n_table,
)

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run opinion trading workflow")
    parser.add_argument(
        "--mode",
        type=str,
        default="daily",
        choices=[
            "daily",
            "realtime",
            "train",
            "evaluate",
            "walk_forward",
            "replay-batch",
            "backtest",
            "factor_backtest",
            "sync_universe",
            "optimize",
            "visualize",
        ],
        help="Execution mode",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().date().isoformat(),
        help="Run date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.yaml",
        help="Path to config file",
    )
    parser.add_argument(
        "--start-date", type=str, default="2025-01-01", help="Backtest start date"
    )
    parser.add_argument(
        "--end-date", type=str, default="2025-12-31", help="Backtest end date"
    )
    parser.add_argument(
        "--bearish-threshold",
        type=float,
        default=-0.6,
        help="Bearish threshold for backtest",
    )
    parser.add_argument(
        "--platforms",
        type=str,
        default="guba,eastmoney,sina_finance,xueqiu,weibo",
        help="Comma-separated platform list for backtest",
    )
    parser.add_argument(
        "--multi-agent",
        action="store_true",
        help="Use multi-agent consensus in backtest mode (requires market data)",
    )
    parser.add_argument(
        "--backtest-file",
        type=str,
        default="data/reports/backtest_results.csv",
        help="Backtest CSV path for visualize mode",
    )
    parser.add_argument(
        "--price-file",
        type=str,
        default="data/reports/price_history_template.csv",
        help="Price CSV path for evaluate mode",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Polling iterations for realtime mode",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Sleep interval (seconds) between realtime polls",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=3,
        help="Number of top picks to output in realtime mode",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=6,
        help="Lookback months for training mode",
    )
    parser.add_argument(
        "--alert-threshold",
        type=float,
        default=0.25,
        help="Trigger alert when symbol score change abs(delta) exceeds this threshold in realtime mode",
    )
    parser.add_argument(
        "--yellow-threshold", type=float, default=0.20, help="Yellow alert threshold"
    )
    parser.add_argument(
        "--orange-threshold", type=float, default=0.35, help="Orange alert threshold"
    )
    parser.add_argument(
        "--red-threshold", type=float, default=0.50, help="Red alert threshold"
    )
    parser.add_argument(
        "--fast-daily",
        action="store_true",
        help="Skip web crawl; replay cached data/raw/raw_posts_<date>.csv (demo/CI)",
    )
    parser.add_argument(
        "--reset-paper",
        action="store_true",
        help="Reset paper state.json before replay-batch (P0 backfill)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Configure structured logging
    configure_logging()

    if args.mode == "daily":
        run_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        logger.info("Starting daily workflow for %s", run_date)
        workflow = OpinionTradingWorkflow(config_path=args.config)
        result = workflow.run_daily(run_date, skip_crawl=args.fast_daily)

        logger.info(
            "Daily workflow completed | date=%s signals=%d trades=%d "
            "best_combo=%s report=%s raw_csv=%s cash=%.2f",
            result["run_date"],
            result["signals"],
            result["trades"],
            ",".join(result["best_combo"]),
            result["report"],
            result["raw_csv"],
            result["state"]["cash"],
        )
        return

    if args.mode == "realtime":
        logger.info("Starting realtime workflow")
        workflow = OpinionTradingWorkflow(config_path=args.config)
        result = workflow.run_realtime(
            iterations=args.iterations,
            interval_seconds=args.interval_seconds,
            top_n=args.top_n,
            alert_threshold=args.alert_threshold,
            yellow_threshold=args.yellow_threshold,
            orange_threshold=args.orange_threshold,
            red_threshold=args.red_threshold,
        )
        logger.info(
            "Realtime completed | iterations=%d alerts=%d picks=%d csv=%s",
            result["iterations"],
            len(result.get("alerts", [])),
            len(result.get("picks", [])),
            result.get("report_csv", ""),
        )
        return

    if args.mode == "evaluate":
        from opinion_trading.core.config_loader import load_runtime_config
        from opinion_trading.core.evaluation import evaluate_signals, save_evaluation
        from opinion_trading.core.walk_forward import (
            run_walk_forward,
            save_walk_forward_report,
        )

        runtime = load_runtime_config(args.config)
        signal_path = str(Path(runtime.memory_dir) / "signal_history.jsonl")
        signals = load_signals(signal_path)
        prices = load_prices(args.price_file)
        merged, summary = evaluate_signals(
            signals, prices, args.start_date, args.end_date
        )
        outputs = save_evaluation(runtime.report_dir, merged, summary)
        print("=== Evaluation Completed ===")
        print(f"Output CSV: {outputs['csv']}")
        print(f"Output MD: {outputs['md']}")
        print(f"Total signals: {summary.total_signals}")
        print(f"Accuracy: {summary.accuracy:.2%}")
        print(f"Avg next-day return: {summary.avg_return:.4%}")
        print(f"Win rate: {summary.win_rate:.2%}")
        print(f"Sharpe-like: {summary.sharpe_like:.4f}")
        print(f"Max drawdown: {summary.max_drawdown:.2%}")
        print(f"Profit factor: {summary.profit_factor:.4f}")
        print(f"Payoff ratio: {summary.payoff_ratio:.4f}")
        print(f"Calmar-like: {summary.calmar_like:.4f}")
        if hasattr(summary, "factor_ic"):
            print(f"Factor IC: {summary.factor_ic:.4f}")
            print(f"Excess return ann: {summary.excess_return_ann:.2%}")
        wf = runtime.walk_forward
        if wf and wf.enabled_in_evaluate:
            wf_report = run_walk_forward(
                signal_path,
                prices,
                n_folds=wf.n_folds,
                train_days=wf.train_days,
                test_days=wf.test_days,
            )
            wf_path = save_walk_forward_report(runtime.report_dir, wf_report)
            print("--- Walk-Forward (out-of-sample) ---")
            print(f"Report: {wf_path}")
            print(f"Avg test accuracy: {wf_report.avg_test_accuracy:.2%}")
            print(f"Recommendation: {wf_report.recommendation}")
        return

    if args.mode == "sync_universe":
        from opinion_trading.core.settings_patch import update_universe_symbols
        from opinion_trading.core.symbol_map import SymbolMapper, SEED_ALIAS_MAP
        from opinion_trading.core.universe import ensure_universe_file, load_index_constituents

        symbols = load_index_constituents("hs300", max_symbols=30, use_akshare=True)
        ensure_universe_file("config/universe_focus.json", index="hs300", max_symbols=30)
        update_universe_symbols(args.config, symbols)
        mapper = SymbolMapper(SEED_ALIAS_MAP)
        mapper.save_json("config/symbol_alias_map.json")
        print("=== Universe Synced ===")
        print(f"Symbols ({len(symbols)}): {', '.join(symbols[:12])}...")
        print("Wrote config/universe_focus.json + config/symbol_alias_map.json")
        print(f"Updated universe in {args.config}")
        return

    if args.mode == "factor_backtest":
        from opinion_trading.core.config_loader import load_runtime_config
        from opinion_trading.core.factor_backtest import (
            fetch_hs300_benchmark,
            run_factor_backtest,
            save_factor_backtest_report,
        )

        runtime = load_runtime_config(args.config)
        prices = load_prices(args.price_file)
        # Build factor panel from sentiment_history or signal confidence
        sent_path = Path(runtime.memory_dir) / "sentiment_history.jsonl"
        sig_path = Path(runtime.memory_dir) / "signal_history.jsonl"
        rows = []
        if sent_path.exists():
            for line in sent_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                import json

                obj = json.loads(line)
                rows.append(
                    {
                        "trade_date": obj.get("trade_date"),
                        "symbol": obj.get("symbol"),
                        "factor": float(obj.get("sentiment_score", 0.0) or 0.0),
                    }
                )
        elif sig_path.exists():
            for line in sig_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                import json

                obj = json.loads(line)
                conf = float(obj.get("confidence", 0.0) or 0.0)
                act = str(obj.get("action", "")).upper()
                factor = conf if act == "BUY" else (-conf if act == "SELL" else conf)
                rows.append(
                    {
                        "trade_date": obj.get("trade_date"),
                        "symbol": obj.get("symbol"),
                        "factor": factor,
                    }
                )
        if not rows:
            print("No sentiment/signal history for factor backtest.")
            return
        factor_df = pd.DataFrame(rows)
        start = args.start_date or str(factor_df["trade_date"].min())[:10]
        end = args.end_date or str(factor_df["trade_date"].max())[:10]
        bench = fetch_hs300_benchmark(start, end)
        report = run_factor_backtest(
            factor_df, prices, benchmark_df=bench, horizons=(1, 3, 5), neutralize=True
        )
        out = save_factor_backtest_report(report, runtime.report_dir, tag="sentiment")
        print("=== Factor Backtest Completed ===")
        print(f"Report: {out}")
        print(f"Obs={report.n_obs} days={report.n_days}")
        for h, st in sorted(report.horizons.items()):
            print(
                f"T+{h}: IC={st['ic_mean']:.4f} ICIR={st['icir']:.4f} "
                f"L/S={st['long_short_excess']:.4%}"
            )
        if report.vs_benchmark:
            print(
                f"Vs HS300 excess_ann={report.vs_benchmark.get('excess_return_ann', 0):.2%} "
                f"sharpe={report.vs_benchmark.get('sharpe', 0):.3f} "
                f"mdd={report.vs_benchmark.get('max_drawdown', 0):.2%}"
            )
        return

    if args.mode == "replay-batch":
        from opinion_trading.core.backfill_signals import run_replay_batch

        summary = run_replay_batch(
            args.config,
            start_date=args.start_date or None,
            end_date=args.end_date or None,
            reset_paper=args.reset_paper,
        )
        print("=== Replay Batch (P0) ===")
        print(f"Dates OK: {summary['dates_run']}/{summary['dates_total']}")
        print(f"Total signals appended: {summary['total_signals']}")
        for row in summary.get("results", []):
            if row.get("ok"):
                print(f"  {row['date']}: signals={row.get('signals', 0)}")
            else:
                print(f"  {row['date']}: FAIL {row.get('error', '')}")
        print("Next: py -m opinion_trading.main --mode walk_forward --price-file ...")
        return

    if args.mode == "walk_forward":
        from opinion_trading.core.config_loader import load_runtime_config
        from opinion_trading.core.evaluation import load_prices
        from opinion_trading.core.walk_forward import (
            run_walk_forward,
            save_walk_forward_report,
        )

        from opinion_trading.core.models import WalkForwardConfig

        runtime = load_runtime_config(args.config)
        wf = runtime.walk_forward or WalkForwardConfig()
        signal_path = str(Path(runtime.memory_dir) / "signal_history.jsonl")
        prices = load_prices(args.price_file)
        report = run_walk_forward(
            signal_path,
            prices,
            n_folds=wf.n_folds,
            train_days=wf.train_days,
            test_days=wf.test_days,
        )
        out = save_walk_forward_report(runtime.report_dir, report)
        print("=== Walk-Forward Completed ===")
        print(f"Report: {out}")
        print(f"Folds: {len(report.folds)}")
        print(f"Avg test accuracy: {report.avg_test_accuracy:.2%}")
        print(f"Avg test Sharpe-like: {report.avg_test_sharpe:.4f}")
        print(report.recommendation)
        return

    if args.mode == "train":
        signal_df = load_training_history("data/memory")
        if signal_df.empty:
            print("=== Training Completed ===")
            print(
                "No signal or realtime pick history found. Run daily or realtime mode first."
            )
            return

        max_trade_date = signal_df["trade_date"].max()
        min_trade_date = max_trade_date - pd.DateOffset(months=max(1, args.months) - 1)
        min_trade_date = min_trade_date.normalize()
        symbols = sorted(signal_df["symbol"].dropna().unique())

        try:
            price_df = fetch_prices_with_timeout(
                symbols,
                min_trade_date.strftime("%Y-%m-%d"),
                max_trade_date.strftime("%Y-%m-%d"),
            )
            if price_df.empty:
                raise ValueError("empty auto-fetched prices")
        except Exception:
            price_df = load_prices(args.price_file)

        monthly_df, summary = build_monthly_training_frame(
            signal_df, price_df, months=args.months
        )
        outputs = save_monthly_training_report("data/reports", monthly_df, summary)

        print("=== Training Completed ===")
        print(f"Output CSV: {outputs['csv']}")
        print(f"Output MD: {outputs['md']}")
        print(f"Output JSON: {outputs['json']}")
        print(f"Months trained: {summary.months_trained}")
        print(f"Range: {summary.start_month} -> {summary.end_month}")
        print(f"Latest month accuracy: {summary.latest_month_accuracy:.2%}")
        print(f"Rolling success rate: {summary.rolling_success_rate:.2%}")
        print(f"Forecast success rate: {summary.forecast_success_rate:.2%}")
        print(f"Forecast direction: {summary.forecast_direction}")
        return

    backtester = StrategyBacktester(config_path=args.config)
    start_date = backtester.parse_date(args.start_date)
    end_date = backtester.parse_date(args.end_date)

    if args.mode == "backtest" and args.multi_agent:
        from opinion_trading.core.backtest_multi_agent import (
            MultiAgentBacktester,
            comparison_to_dataframe,
        )
        from opinion_trading.core.evaluation import load_prices

        backtester = MultiAgentBacktester(config_path=args.config)
        price_df = load_prices(args.price_file) if Path(args.price_file).exists() else pd.DataFrame()
        cmp = backtester.run_comparison(
            start_date=StrategyBacktester.parse_date(args.start_date),
            end_date=StrategyBacktester.parse_date(args.end_date),
            price_df=price_df,
        )
        cmp_df = comparison_to_dataframe(cmp)
        target = "data/reports/backtest_comparison.csv"
        cmp_df.to_csv(target, index=False)
        print("=== Multi-Agent Backtest Comparison ===")
        print(cmp_df.to_string(index=False))
        print(f"\nSentiment Only: acc={cmp.sentiment.eval_summary.accuracy:.2%}, "
              f"sharpe={cmp.sentiment.eval_summary.sharpe_like:.4f}")
        print(f"Multi-Agent:    acc={cmp.multi_agent.eval_summary.accuracy:.2%}, "
              f"sharpe={cmp.multi_agent.eval_summary.sharpe_like:.4f}")
        return

    if args.mode == "backtest":
        platforms: List[str] = [
            x.strip() for x in args.platforms.split(",") if x.strip()
        ]
        result = backtester.run_single(
            start_date=start_date,
            end_date=end_date,
            bearish_threshold=args.bearish_threshold,
            bullish_threshold=backtester.config.strategy.bullish_threshold,
            platforms=platforms,
        )
        target = "data/reports/backtest_single.csv"
        backtester.save_results([result], target)
        print("=== Backtest Completed ===")
        print(f"Output: {target}")
        print(f"Annual return: {result.annual_return:.4f}")
        print(f"Max drawdown: {result.max_drawdown:.4f}")
        print(f"Sharpe: {result.sharpe:.4f}")
        return

    if args.mode == "optimize":
        bearish_values = [-0.8, -0.7, -0.6, -0.5, -0.4]
        results = backtester.optimize(
            start_date=start_date,
            end_date=end_date,
            bearish_values=bearish_values,
        )
        output = "data/reports/backtest_results.csv"
        backtester.save_results(results, output)
        print("=== Optimization Completed ===")
        print(f"Output: {output}")
        if results:
            top = results[0]
            print(
                f"Best: platforms={'+'.join(top.platforms)}, bearish={top.bearish_threshold}, sharpe={top.sharpe:.4f}"
            )
        return

    if args.mode == "visualize":
        rows = load_backtest_csv(args.backtest_file)
        img_out = str(Path("data/reports") / "opt_sharpe_vs_threshold.png")
        plot_sharpe_vs_threshold(rows, img_out)
        print("=== Visualization Completed ===")
        print(f"Image: {img_out}")
        for platforms, ann, mdd, sharpe in top_n_table(rows, n=5):
            print(
                f"Top | {platforms} | annual={ann:.4f} | mdd={mdd:.4f} | sharpe={sharpe:.4f}"
            )
        return


if __name__ == "__main__":
    main()
