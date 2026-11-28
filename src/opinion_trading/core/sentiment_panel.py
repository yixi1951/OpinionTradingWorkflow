"""Symbol–day sentiment measure panel (thesis Q1–Q5)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd

from opinion_trading.core.bullishness import bullishness_from_rows
from opinion_trading.core.signal_weights import combined_post_weight
from opinion_trading.core.time_decay import weighted_mean_scores

# Formal thesis scorers only. OpenClaw is for free-model crawl validation,
# keyword/hybrid/platform-weights are not substitutes for Jev/DeepSeek scores.
THESIS_LLM_SOURCES = frozenset({"jev", "deepseek"})


def _usable_row(row: Mapping[str, Any]) -> bool:
    if bool(row.get("is_noise")):
        return False
    status = str(row.get("capture_status", "") or "").lower()
    if status in {"error", "blocked", "empty", "openclaw_reject"}:
        return False
    if "ai_relevant" in row and row.get("ai_relevant") is False:
        return False
    # OpenClaw authenticity gate when column present
    if "openclaw_validated" in row:
        val = str(row.get("openclaw_validated", "")).strip().lower()
        if val in {"0", "false", "no"}:
            return False
    return True


def _source_of(row: Mapping[str, Any]) -> str:
    return str(row.get("score_source", "") or "").strip().lower()


def _is_thesis_llm_row(row: Mapping[str, Any]) -> bool:
    return _source_of(row) in THESIS_LLM_SOURCES


def _plain_mean(
    rows: Sequence[Mapping[str, Any]],
    *,
    score_key: str,
    fallback_key: str = "keyword_score",
    require_llm_source: bool = False,
) -> float:
    vals: List[float] = []
    for row in rows:
        if require_llm_source and not _is_thesis_llm_row(row):
            continue
        raw = row.get(score_key)
        if raw is None or raw == "":
            if require_llm_source:
                continue
            raw = row.get(fallback_key, 0.0)
        try:
            vals.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not vals:
        return 0.0
    return max(-1.0, min(1.0, sum(vals) / len(vals)))

def _parse_trade_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return pd.to_datetime(value, errors="coerce").date()
    except Exception:
        return None


def measures_for_group(
    rows: Sequence[Mapping[str, Any]],
    trade_date: date,
    *,
    half_life_hours: float = 24.0,
    bull_threshold: float = 0.05,
) -> Dict[str, float]:
    """Compute Mean / Inf / Dict / LLM / Bullishness for one (date, symbol).

    ``sent_llm`` averages only rows with ``score_source`` in {jev, deepseek}.
    Keyword / OpenClaw / influence-weighting are not thesis scoring substitutes.
    """
    usable = [r for r in rows if _usable_row(r)]
    if not usable:
        usable = list(rows)
    llm_rows = [r for r in usable if _is_thesis_llm_row(r)]
    # Mean / Inf aggregate the best available scalar for diagnostics; main paper
    # tables should prefer sent_llm once DS/Jev coverage is adequate.
    sent_mean = _plain_mean(usable, score_key="ai_score", fallback_key="keyword_score")
    sent_dict = _plain_mean(usable, score_key="keyword_score", fallback_key="keyword_score")
    sent_llm = _plain_mean(
        llm_rows,
        score_key="ai_score",
        fallback_key="ai_score",
        require_llm_source=True,
    )
    # Influence = recency × authority/event/user (aggregation robustness only)
    sent_inf = weighted_mean_scores(
        list(usable),
        trade_date,
        half_life_hours=half_life_hours,
        score_key="ai_score",
        fallback_key="keyword_score",
    )
    # Bullishness for the main path uses LLM rows when available.
    bull_base = llm_rows if llm_rows else usable
    bull = bullishness_from_rows(
        bull_base,
        threshold=bull_threshold,
        score_key="ai_score",
        fallback_key="keyword_score" if not llm_rows else "ai_score",
    )
    out = {
        "sent_mean": float(sent_mean),
        "sent_inf": float(sent_inf),
        "sent_dict": float(sent_dict),
        "sent_llm": float(sent_llm),
        "bullishness": float(bull["bullishness"]),
        "agreement": float(bull["agreement"]),
        "attention_m": float(bull["attention_m"]),
        "n_posts": float(len(usable)),
        "n_llm_posts": float(len(llm_rows)),
        "n_bull": float(bull["n_bull"]),
        "n_bear": float(bull["n_bear"]),
        "n_neutral": float(bull["n_neutral"]),
    }
    out["sent_x_m"] = float(sent_inf) * float(bull["attention_m"])
    try:
        out["mean_post_weight"] = float(
            sum(combined_post_weight(r) for r in usable) / max(1, len(usable))
        )
    except Exception:
        out["mean_post_weight"] = 1.0
    return out

def build_sentiment_panel(
    rows: Iterable[Mapping[str, Any]],
    *,
    half_life_hours: float = 24.0,
    bull_threshold: float = 0.05,
) -> pd.DataFrame:
    """Group raw posts by (trade_date, symbol) and emit thesis measure columns."""
    buckets: Dict[tuple, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        td = _parse_trade_date(row.get("trade_date"))
        sym = str(row.get("symbol") or "").strip().upper()
        if td is None or not sym:
            continue
        buckets[(td.isoformat(), sym)].append(row)

    records: List[Dict[str, Any]] = []
    for (td_s, sym), group in sorted(buckets.items()):
        td = date.fromisoformat(td_s)
        measures = measures_for_group(
            group,
            td,
            half_life_hours=half_life_hours,
            bull_threshold=bull_threshold,
        )
        rec = {"trade_date": td_s, "symbol": sym, **measures}
        records.append(rec)
    if not records:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "symbol",
                "sent_mean",
                "sent_inf",
                "sent_dict",
                "sent_llm",
                "bullishness",
                "agreement",
                "attention_m",
                "n_posts",
                "n_llm_posts",
                "n_bull",
                "n_bear",
                "n_neutral",
                "sent_x_m",
                "mean_post_weight",
            ]
        )
    df = pd.DataFrame.from_records(records)
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    return df.sort_values(["trade_date", "symbol"]).reset_index(drop=True)


def load_raw_rows_from_dir(raw_dir: str | Path) -> List[Dict[str, Any]]:
    """Load all raw_posts_*.csv under raw_dir (best-effort)."""
    root = Path(raw_dir)
    rows: List[Dict[str, Any]] = []
    if not root.exists():
        return rows
    for path in sorted(root.glob("raw_posts_*.csv")):
        try:
            chunk = pd.read_csv(path)
        except Exception:
            continue
        rows.extend(chunk.to_dict(orient="records"))
    return rows


def export_sentiment_panel_csv(
    raw_dir: str | Path,
    out_csv: str | Path,
    *,
    half_life_hours: float = 24.0,
    bull_threshold: float = 0.05,
) -> Path:
    panel = build_sentiment_panel(
        load_raw_rows_from_dir(raw_dir),
        half_life_hours=half_life_hours,
        bull_threshold=bull_threshold,
    )
    out = Path(out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out, index=False)
    return out
