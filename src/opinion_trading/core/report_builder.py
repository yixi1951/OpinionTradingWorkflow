from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from opinion_trading.core.models import AggregatedSentiment, PaperTrade, TradeSignal


class DailyReportBuilder:
    def __init__(self, report_dir: str) -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def build(
        self,
        trade_date: str,
        best_platform_combo: List[str],
        combo_scores: Dict[str, float],
        aggregated_today: Dict[str, AggregatedSentiment],
        signals: List[TradeSignal],
        trades: List[PaperTrade],
        state: Dict,
    ) -> Path:
        target = self.report_dir / f"{trade_date}.md"

        lines: List[str] = []
        lines.append(f"# Daily Opinion Trading Report - {trade_date}")
        lines.append("")
        lines.append("## Best Platform Combination")
        lines.append(f"- Selected combo: {', '.join(best_platform_combo)}")
        lines.append(
            f"- Combo score: {combo_scores.get('+'.join(best_platform_combo), 0.0):.4f}"
        )
        lines.append("")
        lines.append("## Sentiment Snapshot")
        for symbol, agg in aggregated_today.items():
            platform_view = ", ".join(
                f"{k}: {v:.3f}" for k, v in agg.platform_scores.items()
            )
            lines.append(f"- {symbol} | avg={agg.average_score:.3f} | {platform_view}")
        lines.append("")

        lines.append("## Signals")
        if signals:
            for row in signals:
                lines.append(
                    f"- {row.symbol} | {row.action} | conf={row.confidence:.2f} | reason={row.reason} | platforms={','.join(row.platforms)}"
                )
        else:
            lines.append("- No actionable signals.")
        lines.append("")

        lines.append("## Paper Trades")
        if trades:
            for trade in trades:
                lines.append(
                    f"- {trade.symbol} | {trade.action} | shares={trade.shares} | price={trade.price:.2f} | cash_after={trade.cash_after:.2f} | {trade.note}"
                )
        else:
            lines.append("- No trades executed.")
        lines.append("")

        lines.append("## Strategy State")
        lines.append(f"- Cash: {state.get('cash', 0.0):.2f}")
        lines.append(f"- Positions: {state.get('positions', {})}")

        target.write_text("\n".join(lines), encoding="utf-8")
        return target
