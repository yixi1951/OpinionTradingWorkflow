from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd

from opinion_trading.agents.workflow import OpinionTradingWorkflow
from opinion_trading.core.backtest import StrategyBacktester
from opinion_trading.core.evaluation import load_prices, load_signals
from opinion_trading.core.monthly_training import (
    build_monthly_training_frame,
    fetch_prices_with_timeout,
    load_training_history,
    save_monthly_training_report,
)
from opinion_trading.core.visualization import (
    load_backtest_csv,
    plot_sharpe_vs_threshold,
    top_n_table,
)


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
            "backtest",
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "daily":
        run_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        workflow = OpinionTradingWorkflow(config_path=args.config)
        result = workflow.run_daily(run_date)

        print("=== Daily Workflow Completed ===")
        print(f"Run date: {result['run_date']}")
        print(f"Signals: {result['signals']}")
        print(f"Trades: {result['trades']}")
        print(f"Best platform combo: {','.join(result['best_combo'])}")
        print(f"Report: {result['report']}")
        print(f"Raw CSV: {result['raw_csv']}")
        for key, value in result.get("raw_sources", {}).items():
            print(f"Raw source CSV [{key}]: {value}")
        for key, value in result.get("failure_logs", {}).items():
            print(f"Failure log [{key}]: {value}")
        print(f"Quality report: {result['quality_report']}")
        print(f"Cash: {result['state']['cash']}")
        return

    if args.mode == "realtime":
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
        print("=== Realtime Workflow Completed ===")
        print(f"Run time: {result['run_time']}")
        print(f"Iterations: {result['iterations']}")
        print(f"Interval seconds: {result['interval_seconds']}")
        print(f"Best platform combo: {','.join(result.get('best_combo', []))}")
        print(f"Realtime picks CSV: {result['report_csv']}")
        print(f"Realtime picks MD: {result['report_md']}")
        print(f"Alert file: {result['alert_file']}")
        print(f"Alert count: {len(result.get('alerts', []))}")
        print(
            "Alert thresholds: "
            f"yellow={result.get('yellow_threshold')} "
            f"orange={result.get('orange_threshold')} "
            f"red={result.get('red_threshold')}"
        )
        for idx, row in enumerate(result.get("picks", []), start=1):
            print(
                f"Top {idx}: {row.get('symbol', '')} | avg_score={float(row.get('avg_score', 0.0)):.4f}"
            )
        return

    if args.mode == "evaluate":
        from opinion_trading.core.evaluation import evaluate_signals, save_evaluation

        signals = load_signals("data/memory/signal_history.jsonl")
        prices = load_prices(args.price_file)
        merged, summary = evaluate_signals(
            signals, prices, args.start_date, args.end_date
        )
        outputs = save_evaluation("data/reports", merged, summary)
        print("=== Evaluation Completed ===")
        print(f"Output CSV: {outputs['csv']}")
        print(f"Output MD: {outputs['md']}")
        print(f"Total signals: {summary.total_signals}")
        print(f"Accuracy: {summary.accuracy:.2%}")
        print(f"Avg next-day return: {summary.avg_return:.4%}")
        print(f"Win rate: {summary.win_rate:.2%}")
        print(f"Sharpe-like: {summary.sharpe_like:.4f}")
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
