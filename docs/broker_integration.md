# 券商 / 执行层（长期实盘化，当前默认 dry-run）

## 适配器

| 类 | 作用 |
|----|------|
| `PaperBrokerAdapter` | 将 `ExecutionIntent` 写入 `execution_intents_*.jsonl`，不下单 |
| `SignalExportAdapter` | CSV 导出供人工 / OMS |
| `SimulationBrokerAdapter` | 按参考价 + 滑点模拟成交，写入 `simulated_fills_*.jsonl` |

配置：`config/settings.yaml` → `execution.mode`（`paper` | `export`），`dry_run: true`。

## 事件审计

`data/memory/event_log.jsonl` 记录：

- `signal_emitted` / `signal_blocked` / `execution_intent` / `paper_fill` / `risk_reject`

信号与成交分离，便于追溯。

## 风控（脚手架）

`core/risk_controls.py`：`max_open_positions`、`max_single_symbol_notional_pct`（与 Kelly 比例对比）。

daily pipeline 在纸面前过滤信号，拒绝写入 `risk_reject` 事件。

## 接入真实券商（未实现）

1. 实现 `BaseBrokerAdapter.submit_intents`，映射 symbol 到柜台代码。
2. 关闭 `dry_run` 前必须：风控、日损上限、幂等订单号。
3. 建议先跑 `SimulationBrokerAdapter` 与纸面账户对齐后再接 API。