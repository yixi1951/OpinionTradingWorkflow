# 实盘就绪对照清单（P0 / P1 / P2）

对照业务要求与仓库实现。状态：✅ 已具备 · ⚠️ 需运维配置 · ❌ 缺失。

## P0 — 必须有

| 要求 | 状态 | 实现位置 |
|------|------|----------|
| 单日亏损上限 | ✅ | `risk.max_daily_loss_pct` → `risk_controls.apply_risk_to_signals` |
| 单笔亏损上限 | ✅ | `risk.max_single_trade_loss_pct` |
| 最大持仓 | ✅ | `risk.max_open_positions` + `max_single_symbol_notional_pct` |
| 最大并发订单 | ✅ | `risk.max_concurrent_orders`（含 `pending_order_count`） |
| 熔断 / Kill Switch | ✅ | `KILL_SWITCH` 环境变量 + `state.trading_halted`；proxy 侧 `openclaw_proxy/risk.py` |
| 下单幂等 `request_id` | ✅ | `IdempotencyStore` + `PaperBrokerAdapter` |
| 信号消费幂等 `event_id` | ✅ | workflow 导出意图前 `remember("signals", event_id)` |
| 回写/审计可追溯 | ✅ | `audit_trail.jsonl`：`decision_to_order` → `order_submitted` / `order_duplicate_skipped` |
| WS 断连重连 + 指数退避 | ✅ | `openclaw_proxy/connection.py`：`async_retry_with_backoff` |
| 心跳检测 | ✅ | `HeartbeatMonitor`（`WS_HEARTBEAT_*`） |
| 状态回补 / 消费续点 | ✅ | `ResumeCursor`：优先 `last_acked_event_id`，否则 `last_sent_request_id`；冷启动不回放历史 |
| dev/staging/prod 分层 | ✅ | `APP_ENV` → `config/settings.{env}.yaml` 叠加 |
| 启动校验必填与范围 | ✅ | `load_and_validate_runtime_config` / `config_validate.py` |
| `.env.example` 最小可运行 + 生产提示 | ✅ | 仓库根目录 `.env.example` |

**恢复后从哪里继续消费（规则）：**

1. 交易侧：同一 `event_id` / `request_id` 重放 → 幂等库拒绝二次提交。
2. WS 侧：重连后 `resume_from()`；未 ack 的 `request_id` 可安全重发（服务端须幂等）。
3. 冷启动（无 cursor）：只发新请求，不回放历史流。

## P1 — 强烈建议

| 要求 | 状态 | 实现位置 |
|------|------|----------|
| 结构化 JSON 日志 | ✅ | `LOG_FORMAT=json`（`log_utils`） |
| 统一 `trace_id` / `order_id` | ✅ | `ExecutionIntent` + `AuditLogger` |
| 决策链路可追溯 | ✅ | 信号 → 风控拒因 → `decision_to_order` → 下单回执 |
| 主流程指标快照 | ✅ | `pipeline_metrics.py` → `data/memory/pipeline_metrics.{prom,json}` |
| 运维告警（熔断/拒单/broker） | ✅ | `AlertNotifier.push_ops_alert`；`OPS_ALERTS_ENABLED`；配 `DINGTALK_WEBHOOK` 等 |
| 失败路径测试：超时/断线 | ✅ | `tests/test_prod_readiness.py` |
| 失败路径：429 / 5xx 风格重试 | ✅ | 同上 + `http_retry.retry_with_backoff` |
| 数据缺失/延迟 | ✅ | `test_missing_market_data_does_not_crash_risk` |
| 重放重复消息 | ✅ | `test_replay_duplicate_signal_event` / 幂等下单 |
| 最小集成测试 | ✅ | `test_minimal_integration_paper_submit` |
| CI：lint + unit + coverage gate | ✅ | `.github/workflows/ci.yml`（ruff → pytest `--cov-fail-under=35` → smoke） |
| 未过门禁禁止合入 main | ⚠️ | Workflow 已写好；需在 GitHub **Branch protection** 勾选 require `lint` + `test` |
| 移除 coverage 产物噪音 | ✅ | `.gitignore` 含 `.coverage` / `coverage.xml`（未入库） |

## P2 — 迭代项

| 要求 | 状态 | 实现位置 |
|------|------|----------|
| `openclaw_ws_proxy` 拆分 | ✅ | 根文件薄封装；`openclaw_proxy/{connection,protocol,scoring,risk,service}.py` |
| 运行手册 / 回滚 / 故障排查 | ✅ | [`docs/RUNBOOK.md`](RUNBOOK.md) |
| Kill Switch 人工接管流程 | ✅ | RUNBOOK「人工接管」节 |
| 纸面净值与评估同价表对齐 | ✅ | `paper_equity.align_paper_vs_eval`；`--mode align-equity` |
| Walk-forward 测试 | ✅ | `tests/test_walk_forward.py` |
| 股票池 constituents 合并 | ✅ | `universe.constituents_file` + `max_symbols` |
| 网关健康检查脚本 | ✅ | `scripts/gateway_health_check.py` |
| Ops 演练脚本 | ✅ | `scripts/ops_drill.py` |
| 本地 SandboxBroker + 对账 | ✅ | `integrations/sandbox_broker.py`；`execution.mode=sandbox` |
| 止盈 / 止损 | ✅ | `risk.stop_loss_pct` / `take_profit_pct` → `generate_exit_signals` |
| 仪表盘密码 | ✅ | `STREAMLIT_DASHBOARD_PASSWORD`（见 `.env.example`） |

## 关 `dry_run` 前硬门禁（D）

以下全部满足前，**禁止**将 `execution.dry_run` 设为 `false` 或对接真实柜台：

1. `replay-batch` → `walk_forward` 样本外结论可接受（非「偏弱/过拟合」硬否决）。
2. `--mode align-equity` 报告 `ok: true`，或人工确认缺口可接受。
3. `execution.mode=sandbox` 连续多日对账：可接受纸面与账本差异后已同步；`recon_mismatch` 无未处理严重漂移。
4. `python scripts/ops_drill.py` 通过（Kill Switch 开/关 + ops 告警路径）。
5. `python scripts/gateway_health_check.py` 在启用 LLM 时通过（或明确 keyword 降级）。
6. GitHub Branch protection 要求 `lint` + `test`。
7. 仪表盘若公网：已设 `STREAMLIT_DASHBOARD_PASSWORD` 或反代鉴权。

## 快速自检

```bash
set PYTHONPATH=src
.\.venv\Scripts\python.exe -m pytest tests/test_prod_readiness.py tests/test_sandbox_broker.py tests/test_paper_eval_align.py tests/test_walk_forward.py -q
python scripts/ops_drill.py
```

生产前再确认：`APP_ENV=prod`、`KILL_SWITCH=0`、`execution.dry_run=true`（未认证实盘前勿关）、审计与幂等目录可写。

## 落地三件套速查

| 支柱 | 能力 | 入口 |
|------|------|------|
| 可观测性 | JSON 日志 + 审计 + `pipeline_metrics.*` + OPS 告警 | `LOG_FORMAT=json` / webhook / `OPS_ALERTS_ENABLED` |
| 可控性 | 风控硬阈值 + SL/TP + `KILL_SWITCH` | `settings.yaml` `risk:` / RUNBOOK |
| 可恢复性 | WS 续点 + 幂等重放 + sandbox 对账 | `ResumeCursor` / `IdempotencyStore` / `sandbox_ledger.json` |
