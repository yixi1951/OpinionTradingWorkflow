# Multi-day crawl persistence

Grow **real** walk-forward history by appending daily `data/raw/raw_posts_<YYYY-MM-DD>.csv` files instead of relying only on `scripts/materialize_wf_history.py` synthetic bundles.

## Layout

- Combined: `data/raw/raw_posts_<date>.csv`
- Per platform: `data/raw/by_source/raw_posts_<date>_<platform>.csv`
- Failures: `data/raw/failures/fetch_failures_<date>.jsonl`
- Journal (optional): `data/raw/crawl_journal.jsonl`

## Commands

```bash
export PYTHONPATH=src SCORING_MODE=keyword OPENCLAW_SKIP_ROW_SCORE=1

# Best-effort collect for today (falls back to --fast-daily replay on crawl errors)
python -m opinion_trading.main --mode collect-persist --date 2026-06-17

# Offline replay only (no network)
python -m opinion_trading.main --mode collect-persist --date 2026-06-17 --fast-daily

# List calendar span and gaps
python -m opinion_trading.main --mode crawl-span

# Optional retention (deletes files older than N days by filename date)
python -m opinion_trading.main --mode collect-persist --date 2026-06-17 --prune-keep-days 90
```

## Walk-forward path

1. Run `collect-persist` on a schedule (cron/systemd) for each trading day.
2. Use `crawl-span` to monitor gaps; backfill missing days manually or via replay.
3. Run `replay-batch` over the date range to rebuild `signal_history.jsonl`.
4. Point `walk_forward` at a real price CSV (`data/reports/price_history_cache.csv`).

Synthetic `materialize_wf_history.py` remains valid for CI and demos when you lack months of live crawl data.
