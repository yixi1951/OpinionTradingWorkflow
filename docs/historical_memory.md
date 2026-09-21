# Historical memory (JSONL recall)

Offline read-only queries over `data/memory/*.jsonl` — no network, no secrets.

## Files

| Kind | File |
|------|------|
| `sentiment` | `sentiment_history.jsonl` |
| `signals` | `signal_history.jsonl` |
| `trades` | `trade_history.jsonl` |
| `events` | `event_log.jsonl` |
| `quality_gate` | `quality_gate_history.jsonl` |

Implementation: `opinion_trading.core.historical_memory`.

## CLI

```bash
export PYTHONPATH=src

# Filtered rows (JSON)
python -m opinion_trading.main --mode memory-query \
  --memory-kind sentiment --symbol 600519.SH --limit 20

# Table output
python -m opinion_trading.main --mode memory-query \
  --memory-kind signals --output-format table

# Compact per-symbol context (for agents / debugging)
python -m opinion_trading.main --mode memory-recall --symbol 600519.SH \
  --lookback-days 14
```

Wrapper script:

```bash
PYTHONPATH=src python scripts/memory_query.py query --kind trades --symbol 600519.SH
PYTHONPATH=src python scripts/memory_query.py recall --symbol 600519.SH
```

## Settings

`config/settings.yaml` → `memory`:

| Key | Default | Meaning |
|-----|---------|---------|
| `recall_enabled` | `false` | Attach recall snippets to daily signal `explanation` |
| `recall_auto` | `false` | Enable recall only when memory JSONL exists (CI-safe) |
| `lookback_days` | `14` | Window for `recall_symbol_context` |
| `prune_keep_days` | `0` | Drop rows older than N days (0 = off) |

Environment override: `MEMORY_RECALL=1` (force on) or `MEMORY_RECALL=0` (force off).

When recall is active, `run_daily` builds a per-symbol map and appends a one-line
**历史记忆** snippet to each `TradeSignal.explanation` (keyword / offline safe).

## Streamlit

Dashboard → expander **历史记忆**: query by kind/symbol and inspect recall JSON for one symbol.

## Retention

Optional `memory.prune_keep_days` runs at end of `run_daily` and rewrites JSONL in place
(by `trade_date`). Default off; tests use temporary directories only.
