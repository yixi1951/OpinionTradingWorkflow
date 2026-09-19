# 券商 / 执行层（长期实盘化，当前默认 dry-run）

## 模式对照

| 模式 / 类 | 是否下单 | 产出 | 用途 |
|-----------|----------|------|------|
| **Paper** (`PaperBrokerAdapter` + `PaperTradingSkill`) | 否 | `state.json`、`trade_history.jsonl`、`paper_fill` 事件 | 研究用纸面账户与净值 |
| **Sandbox** (`SandboxBrokerAdapter`) | 否 | `sandbox_intents_*.jsonl`，`live_order=False` | 审计 dry-run 意图，对齐未来柜台字段 |
| **Export** (`SignalExportAdapter`) | 否 | `signals_export_*.csv` | 人工 / OMS 导入 |
| **Simulation** (`SimulationBrokerAdapter`) | 否 | `simulated_fills_*.jsonl` | 按参考价 + 滑点模拟撮合 |
| **Live** (`LiveBrokerAdapter` stub) | **未实现** | — | 显式 `NotImplementedError`，CI 从不调用 |

配置：`config/settings.yaml` → `execution.mode`（`paper` | `export` | `simulation` | `sandbox`），`dry_run: true`。

- **已实现**：sandbox / paper / export / simulation 全部 dry-run，只记意图或模拟成交。
- **未实现**：真实券商 REST/FIX、登录态、资金划转、成交回报、撤单。接 API 前必须保留 `dry_run` 并通过风控评审。

## 适配器契约（`BaseBrokerAdapter`）

所有适配器实现 `submit_intents(intents) -> dict`（dry-run 元数据 + 写入路径）。

可选 live 钩子（默认在基类中 **抛出 `NotImplementedError`**，禁止误触真网）：

- `fetch_account()` — 资金账户
- `fetch_positions()` — 柜台持仓
- `cancel_order(order_id)` — 撤单
- `place_live_order(intent)` — 单笔下单

`LiveBrokerAdapter` 是显式占位类：即使误选也不会发起 HTTP，只会失败 fast。

纸面退出规则（研究脚手架，非柜台 TP/SL）：

- `execution.paper_exit`：`take_profit_pct` / `stop_loss_pct`，使用与 `evaluate_signals` 相同的收盘价表，触发 `paper_exit` 事件并生成纸面 `SELL`。

## 纸面 / 评估成本（同一价表路径）

- `execution.simulation_slippage_bps`（默认 5）
- `execution.fee_bps`（默认 0）
- `evaluate_signals` 从策略收益扣单边成本；纸面成交 `apply_fill_price`（BUY 上浮 / SELL 下调）。MTM 仍用收盘中间价。

## 事件审计

`data/memory/event_log.jsonl` 记录：

- `signal_emitted` / `signal_blocked` / `execution_intent` / `paper_fill` / `paper_exit` / `risk_reject`

信号与成交分离，便于追溯。

## 风控（脚手架）

`core/risk_controls.py`：`max_open_positions`、`max_single_symbol_notional_pct`（与 Kelly 比例对比）。

daily pipeline 在纸面前过滤信号，拒绝写入 `risk_reject` 事件。

## 接入真实券商（仍未实现）

1. 子类化 `BaseBrokerAdapter`（或专用 REST/FIX 模块），实现 `submit_intents` 并映射 symbol → 柜台代码。
2. 关闭 `dry_run` 前必须：风控、日损上限、幂等订单号、Secrets 与审计。
3. 建议先跑 `SandboxBrokerAdapter` + `SimulationBrokerAdapter` 与纸面账户对齐后再接 API。
4. **没有券商仿真柜台 / 资金账户对接**；当前仅研究原型。
