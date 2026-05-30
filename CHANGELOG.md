# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- Initial project scaffolding and CI

### 2026-05-31

- Add fallback price-matching behavior when signal dates do not directly overlap price dates: use per-symbol `merge_asof` to match signals to the nearest prior available price and compute next-day returns where possible.
- Ensure merged evaluation frame has a canonical `symbol` column after merges and drop temporary `symbol_x`/`symbol_y` columns.
- Avoid matching to terminal price rows without a computable `next_return` (drop such rows before asof matching).
- Emit a `UserWarning` when fallback matching is used so runs are observable in logs.
- This fixes training runs that previously produced zero monthly rows when local price CSVs lacked signal-date coverage.
