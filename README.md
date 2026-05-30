# 基于 OpenClaw 的自动化舆情选股与投研系统

这是一个可落地的个人项目模板，目标是打通一条完整链路：

- 采集真实平台舆情
- 计算情绪并生成交易信号
- 执行模拟交易
- 产出日报、原始证据链、质量报告

新手建议先看 [d
ocs/beginner_tutorial_zh.md](docs/beginner_tutorial_zh.md)。

## 1. 你能得到什么

- 多智能体流水线：采集员 -> 分析师 -> 交易员 -> 报告员
- 可复现实验产物：memory、日报、回测、可视化
- 证据链产物：按平台拆分的原始帖子 CSV + 失败日志
- 自动质量评估：标题覆盖率、时间覆盖率、正文覆盖率、噪声率

## 2. 具体流程与操作步骤

### 步骤 1：进入项目并激活环境

```powershell
cd C:\Users\ASUS\Desktop\project
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 提示脚本执行受限：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 步骤 2：安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 步骤 3：运行 daily 主流程

```powershell
python run_pipeline.py --mode daily --date 2026-03-15
```

### 步骤 4：核对运行结果（最重要）

运行完成后检查：

- 日报：`data/reports/2026-03-15.md`
- 总原始 CSV：`data/raw/raw_posts_2026-03-15.csv`
- 按来源原始 CSV：
  - `data/raw/by_source/raw_posts_2026-03-15_guba.csv`
  - `data/raw/by_source/raw_posts_2026-03-15_sina_finance.csv`
  - `data/raw/by_source/raw_posts_2026-03-15_weibo.csv`
- 抓取失败日志：`data/raw/failures/fetch_failures_2026-03-15.jsonl`
- 质量报告：`data/reports/quality_2026-03-15.md`

### 步骤 5：解读证据链字段

原始 CSV 关键字段：

- `title`：帖子标题
- `summary`：标题 + 正文摘要，用于快速人工验收
- `post_time`：解析出的发布时间
- `content`：正文截断内容
- `capture_status`：抓取状态，常见值 `success` / `fallback`
- `failure_reason`：抓取失败或回退原因

### 步骤 6：继续做回测与优化（可选）

```powershell
python run_pipeline.py --mode backtest --start-date 2025-01-01 --end-date 2025-12-31 --bearish-threshold -0.6 --platforms guba,eastmoney,sina_finance,xueqiu,weibo
python run_pipeline.py --mode optimize --start-date 2025-01-01 --end-date 2025-12-31
python run_pipeline.py --mode visualize --backtest-file data/reports/backtest_results.csv
```

### 步骤 7：实时模式（OpenClaw 舆情 -> AI 选股）

先设置 OpenClaw 地址（本地 stub 或真实服务都可）：

```powershell
$env:OPENCLAW_URL = "http://127.0.0.1:18080"
Remove-Item Env:OPENCLAW_TOKEN -ErrorAction SilentlyContinue
```

运行实时轮询（每 60 秒一轮，共 30 轮）：

```powershell
python run_pipeline.py --mode realtime --iterations 30 --interval-seconds 60 --top-n 3 --alert-threshold 0.25 --yellow-threshold 0.20 --orange-threshold 0.35 --red-threshold 0.50
```
默认会同时分析多个大众舆情来源，并按权重聚合：`guba`、`eastmoney`、`sina_finance`、`xueqiu`、`weibo`。
如果某个来源暂时不可用，会自动回退到 stub，保证流程继续。

告警分级规则（按分数变化绝对值 abs(delta)）：

- YELLOW：>= `yellow-threshold`
- ORANGE：>= `orange-threshold`
- RED：>= `red-threshold`

说明：`alert-threshold` 会作为最小黄线阈值下限（即 `effective_yellow=max(alert-threshold, yellow-threshold)`）。

输出文件：

- `data/reports/realtime_picks_*.csv`：实时选股榜单
- `data/reports/realtime_picks_*.md`：实时轮询摘要
- `data/reports/realtime_alerts_*.jsonl`：分数突变告警
- `data/memory/realtime_alerts.jsonl`：告警历史累计

一键守护（中断自动重启）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_realtime_guard.ps1 -OpenClawUrl "http://127.0.0.1:18080" -Iterations 10 -IntervalSeconds 30 -TopN 3 -AlertThreshold 0.25 -YellowThreshold 0.20 -OrangeThreshold 0.35 -RedThreshold 0.50
```

如果你有真实 OpenClaw token：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_realtime_guard.ps1 -OpenClawUrl "https://your-openclaw-host" -OpenClawToken "your-token" -Iterations 10 -IntervalSeconds 30 -TopN 3 -AlertThreshold 0.25 -YellowThreshold 0.20 -OrangeThreshold 0.35 -RedThreshold 0.50
```

### 步骤 8：告警推送配置（钉钉 / 企业微信 / Telegram）

按需设置环境变量，未设置的渠道会自动跳过。

```powershell
# 钉钉机器人 Webhook
$env:DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=..."

# 企业微信群机器人 Webhook
$env:WECOM_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."

# Telegram Bot
$env:TELEGRAM_BOT_TOKEN = "123456:ABCDEF..."
$env:TELEGRAM_CHAT_ID = "123456789"
```

推送内容包含：`symbol`、`severity`、`direction`、`delta`、前后分数、时间戳。

### 步骤 9：Windows 计划任务常驻运行（推荐）

先预览将要注册的任务（不落地）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_realtime_task.ps1 -TaskName "OpinionTradingRealtimeGuard" -OpenClawUrl "http://127.0.0.1:18080" -DryRun
```

正式注册常驻任务（开机/登录自动启动）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_realtime_task.ps1 -TaskName "OpinionTradingRealtimeGuard" -OpenClawUrl "http://127.0.0.1:18080"
```

常用管理命令：

```powershell
Start-ScheduledTask -TaskName "OpinionTradingRealtimeGuard"
Stop-ScheduledTask -TaskName "OpinionTradingRealtimeGuard"
Unregister-ScheduledTask -TaskName "OpinionTradingRealtimeGuard" -Confirm:$false
```

### 步骤 10：UI 可视化面板（给客户演示用）

启动 UI：

```powershell
streamlit run src/opinion_trading/ui_dashboard.py
```

面板包含：

- 实时选股榜单与告警
- 平台情绪趋势图
- 选股依据（Top 正/负评论）
- 月度正确率与性价比（基于价格数据）

价格数据获取方式：

- 默认 UI 中勾选“Auto fetch prices (Yahoo)”自动拉取
- 或手动准备 CSV 并关闭自动拉取

### 步骤 11：多月评论回测正确率分析

准备价格数据 CSV（字段必须包含）：

```
date,symbol,close
2026-03-13,600519.SH,1500.0
2026-03-14,600519.SH,1520.0
```

模板文件已提供：`data/reports/price_history_template.csv`

运行评估：

```powershell
python run_pipeline.py --mode evaluate --price-file data/reports/price_history_template.csv --start-date 2026-03-01 --end-date 2026-05-31
```

输出：

- `data/reports/accuracy_eval_*.csv`：逐条信号的正确性
- `data/reports/accuracy_eval_*.md`：汇总正确率与性价比（Sharpe-like）

### 步骤 12：回归测试与在线端到端验证

离线回归测试：

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

要使用 `pytest` 运行新增测试：

```powershell
pip install -r requirements-dev.txt
pytest -q
```


在线端到端验证（使用仓库内的 OpenClaw 兼容 stub）：

```powershell
python -m uvicorn openclaw_stub:app --host 127.0.0.1 --port 18080
```

另开一个终端运行：

```powershell
$env:OPENCLAW_URL = "http://127.0.0.1:18080"
python run_pipeline.py --mode realtime --iterations 1 --interval-seconds 1 --top-n 1 --alert-threshold 0.25 --yellow-threshold 0.20 --orange-threshold 0.35 --red-threshold 0.50
```

### 可选：当你的 OpenClaw 只提供 WebSocket 网关时（使用项目内代理）

如果你得到的接入信息是 WebSocket 地址 + 网关令牌（例如：`ws://localhost:18789` 和 `6f75...`），
可用仓库内的小型代理把 REST 请求转成 WebSocket 调用：

1. 安装依赖（已将 `websockets` 添加到 `requirements.txt`）：

```powershell
python -m pip install -r requirements.txt
```

2. 在一台可访问该网关的主机启动代理：

```powershell
# 让代理连接到你的网关地址/令牌（默认为 ws://localhost:18789）
$env:WS_GATEWAY_URL = "ws://localhost:18789"
$env:WS_GATEWAY_TOKEN = "6f751f53aed82616bb4288d8d4a0c16a06afc062f15fb202"

# 启动代理（默认对外监听 18790）
python -m uvicorn openclaw_ws_proxy:app --host 127.0.0.1 --port 18790
```

3. 在项目中把 `OPENCLAW_URL` 指向代理：

```powershell
$env:OPENCLAW_URL = "http://127.0.0.1:18790"
Remove-Item Env:OPENCLAW_TOKEN -ErrorAction SilentlyContinue
python run_pipeline.py --mode realtime --iterations 1 --interval-seconds 1 --top-n 1
```

说明：代理实现的是通用模式（先发 `{"op":"auth","token":...}` 再发 `{"op":"score","id":...,"texts":[...]}`），
如果你的网关使用不同消息格式，请告诉我网关的消息规范，我会调整代理以匹配。

可配置项：

```powershell
$env:WS_GATEWAY_AUTH_TEMPLATE = '{"type":"login","token":"{{token}}"}'
$env:WS_GATEWAY_REQUEST_TEMPLATE = '{"type":"infer","req_id":"{{id}}","payload":{{texts_json}}}'
$env:WS_GATEWAY_SCORE_KEYS = 'scores,data.scores,data.result.scores'
$env:WS_GATEWAY_AUTH_TIMEOUT = '1'
$env:WS_GATEWAY_RESPONSE_TIMEOUT = '10'
```

模板占位符：`{{token}}`、`{{id}}`、`{{texts_json}}`。


## 3. 代码结构与每个文件的用途

### 3.1 入口与执行控制

- `run_pipeline.py`
用途：项目启动入口。把 `src` 加入路径后调用主程序。

- `src/opinion_trading/main.py`
用途：命令行参数解析与模式分发（daily/realtime/evaluate/backtest/optimize/visualize）。

### 3.2 工作流与角色层

- `src/opinion_trading/agents/workflow.py`
用途：全流程总编排。顺序执行原始采集、质量报告、情绪分析、模拟交易、日报写入；并支持实时轮询选股与分数变化告警。

- `scripts/run_realtime_guard.ps1`
用途：实时模式守护脚本。进程中断后自动重启，适合长时间运行。

- `scripts/register_realtime_task.ps1`
用途：注册 Windows 计划任务，让实时守护脚本在开机/登录后自动常驻运行。

- `src/opinion_trading/ui_dashboard.py`
用途：Streamlit UI 可视化面板，展示 OpenClaw 选股、评论解释与正确率分析。

- `src/opinion_trading/core/evaluation.py`
用途：多月评论回测正确率分析（需提供价格 CSV）。

- `src/opinion_trading/agents/roles.py`
用途：定义 Collector/Analyst/Trader 三个角色，解耦职责，便于替换某一层实现。

### 3.3 采集与平台集成层

- `src/opinion_trading/integrations/platform_sentiment_real.py`
用途：真实网页采集与解析核心。负责：
1. 构造平台 URL
2. 下载页面并解析标题/时间/正文
3. 生成 `summary`、`capture_status`、`failure_reason`
4. 失败时回退 fallback/stub，保证流程不中断

- `src/opinion_trading/integrations/platform_sentiment_stub.py`
用途：演示和兜底数据源。真实抓取失败时可回退，确保流程可运行。

### 3.4 Skill 层（业务逻辑）

- `src/opinion_trading/skills/sentiment_collection.py`
用途：按日期、股票、平台拉取快照，生成 `OpinionSnapshot`。

- `src/opinion_trading/skills/sentiment_analysis.py`
用途：计算聚合情绪、平台组合评分、交易信号。

- `src/opinion_trading/skills/trade_simulation.py`
用途：根据信号执行模拟交易，维护现金和持仓状态。

### 3.5 核心基础设施

- `src/opinion_trading/core/config_loader.py`
用途：加载 `config/settings.yaml`，转为运行时配置对象。

- `src/opinion_trading/core/models.py`
用途：集中定义数据结构（快照、信号、交易、原始帖子等）。

- `src/opinion_trading/core/memory_store.py`
用途：JSONL/JSON 持久化（舆情历史、信号历史、交易历史、状态）。

- `src/opinion_trading/core/raw_store.py`
用途：证据链落盘。
1. 写总原始 CSV
2. 按来源拆分 CSV
3. 写失败日志 JSONL

- `src/opinion_trading/core/quality_report.py`
用途：自动计算四项质量指标并输出 Markdown 质量报告。

- `src/opinion_trading/core/report_builder.py`
用途：生成每日策略报告（组合、快照、信号、交易、账户状态）。

- `src/opinion_trading/core/backtest.py`
用途：历史区间回测与参数优化。

- `src/opinion_trading/core/metrics.py`
用途：计算年化收益、最大回撤、夏普等指标。

- `src/opinion_trading/core/visualization.py`
用途：把回测结果画成图并生成 TopN 结果展示。

## 4. 配置文件用途

- `config/settings.yaml`
用途：项目主配置。
包含平台列表、阈值、股票池、内存目录、报告目录、原始数据目录。

- `config/openclaw_tasks.yaml`
用途：OpenClaw 任务模板和自动化指令。

## 5. 产物文件用途

- `data/memory/sentiment_history.jsonl`：每次采集快照历史
- `data/memory/signal_history.jsonl`：交易信号历史
- `data/memory/trade_history.jsonl`：模拟交易历史
- `data/memory/state.json`：账户状态（现金/持仓）
- `data/reports/YYYY-MM-DD.md`：日报
- `data/reports/quality_YYYY-MM-DD.md`：质量报告
- `data/reports/realtime_picks_*.csv`：实时选股榜单
- `data/reports/realtime_picks_*.md`：实时轮询报告
- `data/reports/realtime_alerts_*.jsonl`：实时告警落盘
- `data/reports/accuracy_eval_*.csv`：正确率评估结果
- `data/reports/accuracy_eval_*.md`：正确率评估摘要
- `data/raw/raw_posts_YYYY-MM-DD.csv`：总原始帖子证据
- `data/raw/by_source/*.csv`：按平台拆分的原始证据
- `data/raw/failures/*.jsonl`：抓取失败证据

## 6. 完成项目的验收建议

建议连续跑 7 天，每天都检查质量报告：

- 标题覆盖率 >= 95%
- 时间覆盖率 >= 90%
- 正文覆盖率 >= 85%
- 噪声率 <= 20%

并确保 `fallback` 比例逐步下降。

## 7. 常见问题

- 问：为什么有时会出现 `fallback` 行？
答：页面结构变化或反爬导致解析失败，系统会回退以保证任务不中断。

- 问：如何判断采集是否稳定？
答：看质量报告和失败日志，而不是只看命令行是否报错。

- 问：下一步该优化哪里？
答：优先优化 `src/opinion_trading/integrations/platform_sentiment_real.py` 的解析规则，先压低 fallback，再优化信号策略。

## 8. 你接下来该怎么做（执行清单）

建议按下面顺序推进，不要并行做太多事：

### 第 1 阶段：本地稳定（1-3 天）

目标：本地 daily 连续稳定，证据链完整。

1. 连续运行 3 天 daily。
2. 每天检查：
  - `data/raw/by_source/` 是否有当日三个平台 CSV
  - `data/raw/failures/` 是否有失败日志
  - `data/reports/quality_YYYY-MM-DD.md` 是否生成
3. 记录每日四项指标和 fallback 比例。

通过标准：

- 连续 3 天 daily 不报错
- 质量报告可正常生成
- `capture_status=success` 占比达到你设定阈值（建议先 >= 80%）

### 第 2 阶段：抓取优化（3-7 天）

目标：把 fallback 和噪声率压低。

1. 优先优化 `guba` 解析规则。
2. 再优化 `sina_finance` 时间/正文提取。
3. 每次改动后只跑一次 daily 验证，不要一次改很多逻辑。

通过标准：

- 连续 3 天 `quality_YYYY-MM-DD.md` 的 Overall 为 PASS
- 噪声率 <= 20%
- 时间覆盖率 >= 90%

### 第 3 阶段：策略与展示（2-4 天）

目标：把“能跑”变成“能展示”。

1. 跑 backtest / optimize / visualize。
2. 整理结果图和对比表。
3. 在 README 和 docs 里补一段结论：什么参数组合最好、为什么。

## 9. 什么时候可以连接服务器和 OpenClaw

结论先说：

- 本地链路没稳定前，不建议上服务器和 OpenClaw。
- 满足下面的 Ready 条件后再接，效率最高、排障成本最低。

### 9.1 Ready 条件（全部满足再接）

1. 本地连续 3 天 daily 成功。
2. 每天都有完整证据链文件：raw CSV / by_source CSV / failures / quality report。
3. 质量报告连续 3 天 Overall = PASS。
4. 你能解释每个核心文件用途（本 README 第 3 节）。

### 9.2 连接时机建议

- 最早时机：完成第 2 阶段后。
- 最佳时机：完成第 3 阶段后（有稳定抓取 + 有回测结果 + 有展示材料）。

### 9.3 先接服务器，后接 OpenClaw（推荐顺序）

1. 先把项目部署到服务器，保证纯命令行可跑：
  - 安装依赖
  - 跑 daily
  - 生成相同产物
2. 再接 OpenClaw 调度：
  - 用 `config/openclaw_tasks.yaml` 先跑最小任务
  - 再接 daily 全流程

原因：

- 先排除环境问题（服务器）
- 再排除编排问题（OpenClaw）
- 故障定位会快很多

### 9.4 服务器和 OpenClaw 接入后要做的验证

1. 与本地同一天同参数跑一次，比较关键输出。
2. 检查路径权限（`data/raw/`、`data/reports/` 是否可写）。
3. 检查定时任务重复执行时是否会覆盖关键证据文件。

建议做法：

- 保留按日期命名产物
- 失败日志单独目录保存
- 每日任务结束后输出一行摘要（signals/trades/quality status）