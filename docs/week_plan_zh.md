# 分阶段实施清单（6 周）

## Week 1：OpenClaw 部署与基础能力验证

- 安装 OpenClaw、配置 LLM API Key、安装 Chrome。
- 使用 `config/openclaw_tasks.yaml` 中的 `week1_validation.browser_file_test` 指令做冒烟测试。
- 验收标准：桌面成功生成 `guba_test.txt`，包含评论标题和时间。

## Week 2-3：核心 Skill 开发

- Skill 1：多平台舆情采集员
- Skill 2：情绪共振分析师
- Skill 3：模拟交易执行官
- 在本仓库中，技能接口代码位于 `src/opinion_trading/skills/`，OpenClaw 指令模板位于 `config/openclaw_tasks.yaml`。
- 验收标准：`data/memory/` 与 `data/reports/` 产生可追溯输出。

## Week 4：自动化编排

- 每日定时执行：采集 -> 分析 -> 交易 -> 报告。
- 运行命令：
  - `python run_pipeline.py --mode daily --date 2026-03-15`
- 验收标准：日报文件生成，且包含信号、交易、策略状态。

## Week 5：回测与参数优化

- 单次回测：
  - `python run_pipeline.py --mode backtest --start-date 2025-01-01 --end-date 2025-12-31 --bearish-threshold -0.6 --platforms guba,sina_finance,weibo`
- 网格优化：
  - `python run_pipeline.py --mode optimize --start-date 2025-01-01 --end-date 2025-12-31`
- 验收标准：生成 `data/reports/backtest_results.csv`，并输出最佳参数组合。

## Week 6：可视化与简历包装

- 生成优化图：
  - `python run_pipeline.py --mode visualize --backtest-file data/reports/backtest_results.csv`
- 补全 README：架构图、演示视频、回测对比表、3 个 Skill 代码片段。
- 验收标准：README 对外可读，项目可复现。
