# Transaction costs (research scaffold)

**Not legal or tax advice.** This module approximates mainland A-share style **one-way** costs for offline backtests and paper fills.

## What is modeled

| Component | When applied | Config |
|-----------|--------------|--------|
| Base commission | Every fill | `execution.fee_bps` (legacy flat bps) |
| Tier commission | When `transaction_costs.enabled` | `execution.transaction_costs.commission_tiers` by notional (CNY) |
| Stamp duty (印花税) | **SELL only**, when enabled | `execution.transaction_costs.stamp_tax_calendar` (effective dates) |
| Slippage | Every fill | `execution.simulation_slippage_bps` (unchanged) |

Default `enabled: false` keeps CI and offline demos identical to pre-scaffold behavior.

## Shared code path

`apply_fill_price` / `evaluate_signals` / `PaperTradingSkill` / paper TP/SL exits all resolve fees through `resolve_one_way_fee_bps` when the calendar is enabled.

## Enable locally

```yaml
execution:
  fee_bps: 0.0
  transaction_costs:
    enabled: true
```

Or `TRANSACTION_COSTS=1` for a quick toggle without editing YAML.

Fixture for unit tests: `tests/fixtures/transaction_cost_calendar.yaml`.

## Still deferred

- Per-broker negotiated tiers, minimum commission (元), transfer fees, ETF/可转债 rules
- Live broker fee APIs and settlement calendars
