"""Glue: sentiment panel + prices → FM / Logit thesis tables."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from opinion_trading.core.direction_logit import run_direction_logit_grid
from opinion_trading.core.factor_backtest import attach_forward_returns
from opinion_trading.core.fama_macbeth import run_fama_macbeth_grid
from opinion_trading.core.sentiment_panel import (
    build_sentiment_panel,
    export_sentiment_panel_csv,
    load_raw_rows_from_dir,
)

DEFAULT_MEASURES: Sequence[str] = (
    "sent_mean",
    "sent_inf",
    "sent_dict",
    "sent_llm",
    "bullishness",
)


def merge_panel_with_returns(
    panel: pd.DataFrame,
    price_df: pd.DataFrame,
    horizons: Sequence[int] = (1, 3, 5),
) -> pd.DataFrame:
    prices = attach_forward_returns(price_df, horizons=horizons)
    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices["symbol"] = prices["symbol"].astype(str).str.upper()
    work = panel.copy()
    work["trade_date"] = pd.to_datetime(work["trade_date"], errors="coerce")
    work["symbol"] = work["symbol"].astype(str).str.upper()
    ret_cols = [f"ret_{h}d" for h in horizons]
    merged = work.merge(
        prices[["date", "symbol", "close", *ret_cols]],
        left_on=["trade_date", "symbol"],
        right_on=["date", "symbol"],
        how="inner",
    )
    # Lagged return control (previous day close-to-close when available)
    prices_sorted = prices.sort_values(["symbol", "date"])
    prices_sorted["lag_ret_1d"] = prices_sorted.groupby("symbol")["close"].pct_change()
    merged = merged.merge(
        prices_sorted[["date", "symbol", "lag_ret_1d"]],
        on=["date", "symbol"],
        how="left",
    )
    return merged


def run_thesis_models(
    panel: pd.DataFrame,
    price_df: pd.DataFrame,
    *,
    measures: Sequence[str] = DEFAULT_MEASURES,
    horizons: Sequence[int] = (1, 3, 5),
    control_cols: Optional[Sequence[str]] = ("lag_ret_1d", "attention_m"),
) -> dict[str, pd.DataFrame]:
    merged = merge_panel_with_returns(panel, price_df, horizons=horizons)
    controls = [c for c in (control_cols or []) if c in merged.columns]
    fm = run_fama_macbeth_grid(
        merged,
        measures=measures,
        horizons=horizons,
        control_cols=controls,
    )
    logit = run_direction_logit_grid(
        merged,
        measures=measures,
        horizons=horizons,
        control_cols=controls,
    )
    return {"panel_merged": merged, "fama_macbeth": fm, "logit": logit}


def save_thesis_model_reports(
    results: dict[str, pd.DataFrame],
    report_dir: str | Path,
    *,
    tag: str = "thesis",
) -> dict[str, Path]:
    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for key in ("fama_macbeth", "logit", "panel_merged"):
        df = results.get(key)
        if df is None:
            continue
        path = out_dir / f"{tag}_{key}.csv"
        df.to_csv(path, index=False)
        paths[key] = path
    # Markdown summary
    md = out_dir / f"{tag}_models.md"
    lines = [
        f"# Thesis models ({tag})",
        "",
        "## Fama–MacBeth",
        "",
        results["fama_macbeth"].to_string(index=False)
        if not results["fama_macbeth"].empty
        else "(empty)",
        "",
        "## Logit",
        "",
        results["logit"].to_string(index=False)
        if not results["logit"].empty
        else "(empty)",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    paths["markdown"] = md
    return paths


def build_and_run_from_raw(
    raw_dir: str | Path,
    price_df: pd.DataFrame,
    report_dir: str | Path,
    *,
    panel_csv: Optional[str | Path] = None,
) -> dict[str, Path]:
    rows = load_raw_rows_from_dir(raw_dir)
    panel = build_sentiment_panel(rows)
    if panel_csv:
        Path(panel_csv).parent.mkdir(parents=True, exist_ok=True)
        panel.to_csv(panel_csv, index=False)
    results = run_thesis_models(panel, price_df)
    return save_thesis_model_reports(results, report_dir)


__all__ = [
    "DEFAULT_MEASURES",
    "build_and_run_from_raw",
    "export_sentiment_panel_csv",
    "merge_panel_with_returns",
    "run_thesis_models",
    "save_thesis_model_reports",
]
