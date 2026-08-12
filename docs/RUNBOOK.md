# 运行手册与应急预案

## 环境分层

| `APP_ENV` | 配置叠加 | 用途 |
|-----------|----------|------|
| `dev` | `config/settings.dev.yaml` | 本地开发，宽松风控 |
| `staging` | `config/settings.staging.yaml` | CI / 预发，keyword 评分 |
| `prod` | `config/settings.prod.yaml` | 生产，更严风控；默认 `dry_run: true` |

启动时 `OpinionTradingWorkflow` 会校验必填项与风控取值范围；失败直接抛错。

最小本地运行：

```bash
cp .env.example .env
# 保持 SCORING_MODE=keyword、BROWSER_COLLECT_ENABLED=0
set PYTHONPATH=src
python -m opinion_trading.main --mode daily --date 2026-06-17 --fast-daily
```

## 部署

1. 设置 `APP_ENV=staging|prod`，复制 `.env.example` → `.env`，填入密钥（勿入库）。
2. 确认 `KILL_SWITCH=0`，`execution.dry_run=true`（未认证实盘前禁止关闭）。
3. 安装依赖：`pip install -r requirements.txt`；若启用浏览器采集再装 Playwright Chromium。
4. 可选：启动 `openclaw_ws_proxy.py` / 推理服务；否则用 keyword 模式。
5. 跑一次 `--fast-daily` 冒烟，确认 `data/memory/state.json` 与审计文件生成。

## 回滚

1. 将代码回退到上一发布 tag / commit。
2. 恢复上一版 `config/settings.prod.yaml` 与 `.env`（不含密钥提交）。
3. 若状态异常：备份 `data/memory/state.json`，用最近已知良好副本替换，或清空当日 `pending_order_count` 后人工核对持仓。
4. 重新 `--fast-daily` 验证导出意图不再重复（幂等库在 `data/memory/idempotency/`）。

## 故障排查

| 现象 | 检查 |
|------|------|
| 全部拒单 | `KILL_SWITCH`、`state.trading_halted`、`audit_trail.jsonl` 中 `risk_reject` / `trading_halted` |
| 重复下单嫌疑 | `data/memory/idempotency/orders.jsonl` 是否已有相同 `request_id` |
| WS 断连 | `WS_GATEWAY_*`、`ws_resume_cursor.json`；重连后从 `resume_from` 继续，未 ack 的 `request_id` 可安全重发 |
| 429 / 5xx | HTTP/WS 层指数退避；持续失败会触发 `halt_on_broker_failure` |
| 行情缺失 | 风控在无价格时仍可按名义比例校验；成交价依赖行情源，检查 `market_data` 日志 |
| 配置错误 | 启动报 `ValueError`：对照 `config_validate` 错误列表修 YAML |

审计链路（JSONL）：`data/memory/audit_trail.jsonl`

事件顺序：`risk_reject` / `decision_to_order` → `order_submitted` →（重复时）`order_duplicate_skipped`。用同一 `trace_id` / `order_id` 过滤即可还原决策。

结构化运行日志：设置 `LOG_FORMAT=json`。

主流程指标：每次 `run_daily` 结束后写入：

- `data/memory/pipeline_metrics.prom`（Prometheus 文本，可用 node_exporter textfile 或手工 scrape）
- `data/memory/pipeline_metrics.json`（含 signals / rejects / halt / positions）

运维告警：`trading_halted`、`risk_reject`（汇总）、`broker_failure` 经 `AlertNotifier.push_ops_alert` 推送钉钉/企微/TG。关闭：`OPS_ALERTS_ENABLED=0`。

## 人工接管（Kill Switch）

**立即停单（秒级）：**

```bash
# 环境变量（进程需能读到；建议配合进程重启或常驻守护热加载）
set KILL_SWITCH=1
```

或在状态中置位（跨进程持久）：

```python
from opinion_trading.core.memory_store import JsonLineMemoryStore
from opinion_trading.core.risk_controls import set_kill_switch

store = JsonLineMemoryStore("data/memory")
state = store.load_state()
store.save_state(set_kill_switch(state, True, reason="manual_ops"))
```

效果：

- 风控 `is_trading_halted` 为真，新信号全部拒绝
- OpenClaw proxy `check_proxy_allowed` 返回 403
- `halt_sticky` 防止隔日自动解除（除非清 kill switch）

**恢复交易：**

```bash
set KILL_SWITCH=0
```

```python
store.save_state(set_kill_switch(store.load_state(), False))
# 如需解除普通熔断：
from opinion_trading.core.risk_controls import clear_trading_halt
store.save_state(clear_trading_halt(store.load_state()))
```

恢复后消费规则：

1. **交易/信号**：幂等键仍有效；重放同一 `event_id` / `request_id` 不会重复下单。
2. **WebSocket**：从 `ResumeCursor.resume_from()` 继续——优先 `last_acked_event_id`（服务端已确认）；否则 `last_sent_request_id`（可安全重发，依赖对端幂等）。
3. **冷启动**（无 cursor 文件）：不回放历史流，只发新请求。

完整对照表见 [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)。

## 网关健康检查

```bash
set PYTHONPATH=src
python scripts/gateway_health_check.py
```

结果写入 `data/reports/gateway_health_*.json`。未配置 `OPENCLAW_URL` / `INFERENCE_URL` 时退出码非 0（可改用 keyword 模式离线运行）。

## Ops 演练（Kill Switch + 告警路径）

```bash
set PYTHONPATH=src
# 可选：OPS_ALERTS_ENABLED=0 仅测状态机、不调 webhook
python scripts/ops_drill.py
```

会短暂打开再关闭 Kill Switch，并推送 `trading_halted` / `risk_reject` / `broker_failure` ops 告警（无 webhook 时仍返回结构化结果）。报告：`data/reports/ops_drill_*.json`。

## 策略验证（A）

```bash
py -m opinion_trading.main --mode replay-batch --start-date 2026-06-01 --end-date 2026-06-17 --reset-paper
py -m opinion_trading.main --mode walk_forward --price-file data/reports/price_history_cache.csv
py -m opinion_trading.main --mode align-equity --price-file data/reports/price_history_cache.csv
```

对齐报告：`data/reports/paper_eval_align_*.md`。

## Sandbox 执行演练（C）

在 `config/settings.yaml`（或 overlay）设 `execution.mode: sandbox`，保持 `dry_run: true`，跑 `--fast-daily`。账本：`data/memory/sandbox_ledger.json`；对账事件见 `audit_trail.jsonl`（`recon_ok` / `recon_mismatch`）。

## 仪表盘鉴权

公网或共享主机务必设置：

```bash
set STREAMLIT_DASHBOARD_PASSWORD=your-strong-password
```

未设置时本地可直接打开（仅适合本机演示）。

## CI 门禁

GitHub Actions：`lint`（ruff）→ `test`（pytest + coverage≥35%）→ `fast-daily-smoke`。

请在仓库 **Settings → Branches → main** 勾选 Require status checks，至少包含 `lint` 与 `test`，未通过禁止合并。

关 `dry_run` 前的完整清单见 [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)「关 dry_run 前硬门禁」。
