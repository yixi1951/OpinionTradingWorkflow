# 券商 / 执行层（长期实盘化，当前默认 dry-run）

## 模式对照

| 模式 / 类 | 是否下单 | 产出 | 用途 |
|-----------|----------|------|------|
| **Paper** (`PaperBrokerAdapter` + `PaperTradingSkill`) | 否 | `state.json`、`trade_history.jsonl`、`paper_fill` 事件 | 研究用纸面账户与净值 |
| **Sandbox** (`SandboxBrokerAdapter`) | 否 | `sandbox_intents_*.jsonl`，`live_order=False` | 审计 dry-run 意图，对齐未来柜台字段 |
| **Export** (`SignalExportAdapter`) | 否 | `signals_export_*.csv` | 人工 / OMS 导入 |
| **Simulation** (`SimulationBrokerAdapter`) | 否 | `simulated_fills_*.jsonl` | 按参考价 + 滑点模拟撮合 |
| **Live** (`LiveBrokerAdapter` stub) | **未实现** | — | 显式 `NotImplementedError`，CI 从不调用 |
| **HTTP sandbox** (`HttpSandboxBrokerAdapter`) | 否（默认关） | 远程 mock/REST `POST /v1/intents` + 本地审计 JSONL | `ENABLE_HTTP_BROKER_SANDBOX=1` |

配置：`config/settings.yaml` → `execution.mode`（`paper` | `export` | `simulation` | `sandbox` | `http_sandbox`），`dry_run: true`。

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

## 本地 HTTP mock 柜台（脚手架）

用于联调 REST 字段，**不会**连接真实交易所：

```bash
export PYTHONPATH=src
python scripts/run_mock_broker.py   # 127.0.0.1:8765
export ENABLE_HTTP_BROKER_SANDBOX=1 BROKER_SANDBOX_URL=http://127.0.0.1:8765
python -m opinion_trading.main --mode broker-sandbox-probe
python -m opinion_trading.main --mode broker-sandbox-probe --start-mock-broker
```

Mock API：

- `GET /health`
- `POST /v1/intents` — 幂等 `order_id`（`client_order_id` 或内容哈希）
- `GET /v1/orders/{order_id}`

`HttpSandboxBrokerAdapter` 始终默认 `dry_run`；`BROKER_SANDBOX_ALLOW_LIVE=1` 仅为文档化危险开关，mock 仍会拒绝真下单。

## 接入真实券商 REST（仍未实现）

| 检查项 | 说明 |
|--------|------|
| `BROKER_SANDBOX_URL` | 券商仿真或 UAT base URL |
| Symbol 映射 | `000001.SZ` → 柜台代码表 |
| 幂等键 | `client_order_id` / 策略批次 id |
| 认证 | API Key / OAuth — **仅环境变量**，勿入库 |
| 风控 | `risk_controls` + 日损上限 |
| 审计 | 保留 `http_sandbox_intents_*.jsonl` 与 `event_log.jsonl` |

步骤：

1. 让 `HttpSandboxBrokerAdapter` 指向券商文档中的 dry-run 端点，或子类化 `BaseBrokerAdapter`。
2. 在 funded 账户前：纸面 + mock HTTP + `SimulationBrokerAdapter` 对齐成交假设。
3. **没有** 默认绑定的券商凭证；生产 REST/FIX 仍属 OUT OF SCOPE 直至你方签约与密钥配置。
