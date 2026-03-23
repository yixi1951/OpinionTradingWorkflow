from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import List

from opinion_trading.agents.workflow import OpinionTradingWorkflow
from opinion_trading.core.backtest import StrategyBacktester
from opinion_trading.core.visualization import load_backtest_csv, plot_sharpe_vs_threshold, top_n_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run opinion trading workflow")
    parser.add_argument(
        "--mode",
        type=str,
        default="daily",
        choices=["daily", "backtest", "optimize", "visualize"],
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
    parser.add_argument("--start-date", type=str, default="2025-01-01", help="Backtest start date")
    parser.add_argument("--end-date", type=str, default="2025-12-31", help="Backtest end date")
    parser.add_argument(
        "--bearish-threshold",
        type=float,
        default=-0.6,
        help="Bearish threshold for backtest",
    )
    parser.add_argument(
        "--platforms",
        type=str,
        default="guba,sina_finance,weibo",
        help="Comma-separated platform list for backtest",
    )
    parser.add_argument(
        "--backtest-file",
        type=str,
        default="data/reports/backtest_results.csv",
        help="Backtest CSV path for visualize mode",
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
        print(f"Cash: {result['state']['cash']}")
        return

    backtester = StrategyBacktester(config_path=args.config)
    start_date = backtester.parse_date(args.start_date)
    end_date = backtester.parse_date(args.end_date)

    if args.mode == "backtest":
        platforms: List[str] = [x.strip() for x in args.platforms.split(",") if x.strip()]
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
            print(f"Top | {platforms} | annual={ann:.4f} | mdd={mdd:.4f} | sharpe={sharpe:.4f}")
        return


if __name__ == "__main__":
    main()
