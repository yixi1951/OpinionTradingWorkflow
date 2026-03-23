# 基于 OpenClaw 智能体的自动化舆情选股与投研系统

这是一个适合大学生个人项目落地的 MVP：

- 多智能体协作：采集员 -> 分析师 -> 交易员 -> 报告员
- 3 个核心 Skill：舆情采集、情绪共振分析、模拟交易
- 持久化记忆：舆情历史、信号历史、交易历史、策略状态
- 自然语言可配置：通过配置文件与任务模板快速迭代

新手先看：`docs/beginner_tutorial_zh.md`

## 1. 项目结构

- `config/`：策略配置、OpenClaw 指令模板
- `data/`：运行产物（memory / reports）
- `docs/`：周计划与架构图
- `src/opinion_trading/agents/`：多智能体角色与工作流
- `src/opinion_trading/skills/`：3 个核心技能代码
- `src/opinion_trading/core/`：配置、存储、报告、回测、可视化
- `src/opinion_trading/integrations/`：平台数据与 OpenClaw 集成适配

## 2. 快速开始

1. 创建并激活 Python 环境。
2. 安装依赖：
   - `pip install -r requirements.txt`
3. 运行日常流程：
   - `python run_pipeline.py --mode daily --date 2026-03-15`
4. 运行回测：
   - `python run_pipeline.py --mode backtest --start-date 2025-01-01 --end-date 2025-12-31 --bearish-threshold -0.6 --platforms guba,sina_finance,weibo`
5. 参数优化：
   - `python run_pipeline.py --mode optimize --start-date 2025-01-01 --end-date 2025-12-31`
6. 生成可视化：
   - `python run_pipeline.py --mode visualize --backtest-file data/reports/backtest_results.csv`

## 3. 你的五阶段实施路径（与仓库对应）

### Week 1：OpenClaw 部署与能力验证

- 按 OpenClaw 官方文档完成部署。
- 配置低成本模型（如 GPT-4o mini / Claude 3.5 Haiku）。
- 使用 `config/openclaw_tasks.yaml` 中 `week1_validation.browser_file_test` 做浏览器+文件写入验证。

### Week 2-3：开发 3 个核心 Skill

- Skill 1《多平台舆情采集员》：对应 `src/opinion_trading/skills/sentiment_collection.py`
- Skill 2《情绪共振分析师》：对应 `src/opinion_trading/skills/sentiment_analysis.py`
- Skill 3《模拟交易执行官》：对应 `src/opinion_trading/skills/trade_simulation.py`
- OpenClaw 指令模板：`config/openclaw_tasks.yaml`

### Week 4：自动化编排

- 编排入口：`src/opinion_trading/agents/workflow.py`
- 日常执行命令：
  - `python run_pipeline.py --mode daily --date 2026-03-15`
- 输出：
  - `data/memory/*.jsonl`
  - `data/reports/YYYY-MM-DD.md`

### Week 5：回测与动态优化

- 回测引擎：`src/opinion_trading/core/backtest.py`
- 指标计算（年化、回撤、夏普）：`src/opinion_trading/core/metrics.py`
- 优化输出：`data/reports/backtest_results.csv`

### Week 6：可视化与简历包装

- 可视化脚本：`src/opinion_trading/core/visualization.py`
- 架构图：`docs/architecture.mmd`
- 周计划：`docs/week_plan_zh.md`

## 4. 多平台情绪共振反转指标

策略核心：

- 买入条件：至少 2 个平台同时出现极度悲观（情绪分 < -0.6），且次日情绪回升（平均增量 >= 0.1）。
- 卖出条件：至少 2 个平台同时出现极度狂热（情绪分 > 0.7）。
- 平台组合优化：自动遍历平台组合与阈值，按夏普比率选最优。

## 5. OpenClaw 自然语言工作流示例

可直接复制到 OpenClaw：

- “每天凌晨 1 点执行以下流程：调用《多平台舆情采集员》采集昨日数据；调用《情绪共振分析师》分析情绪并生成信号；如果有交易信号，调用《模拟交易执行官》执行操作；最后生成 Markdown 日报到 ./data/reports/。”

## 6. README 展示必备（你投递简历时补齐）

- 架构图（建议 draw.io 导出 PNG）
- 30 秒演示视频（录屏 OpenClaw 自动操作浏览器并生成日报）
- 回测对比表（不同参数组合的年化、最大回撤、夏普）
- 3 个核心 Skill 代码片段

示例表头：

| 参数组合 | 年化收益 | 最大回撤 | 夏普比率 |
|---|---:|---:|---:|
| guba+sina, bearish=-0.6 | 0.XX | 0.XX | X.XX |
| guba+weibo, bearish=-0.5 | 0.XX | 0.XX | X.XX |
| guba+sina+weibo, bearish=-0.7 | 0.XX | 0.XX | X.XX |

## 7. 说明

当前仓库默认使用 stub 平台数据，目的是先打通“可运行闭环”。

你下一步只需要替换 `src/opinion_trading/integrations/` 下的数据源适配器，就能接入真实股吧/新浪/微博网页采集与 OpenClaw 浏览器自动化执行。