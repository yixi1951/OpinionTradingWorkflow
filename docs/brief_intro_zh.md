项目简介 — OpenClaw AI 选股

概述
- 名称：OpenClaw AI Picks（项目仓库: OpinionTradingWorkflow）
- 目的：通过多平台舆情抓取与情感分析，为股票选股与短期交易决策提供辅助信号与可解释的选股理由。

主要功能
- 多平台情感抓取：支持 guba、weibo、sina_finance、eastmoney、xueqiu，以及新增的 douyin（示例数据）。
- 情感聚合：在 pandas 层做按月与按平台的聚合，支持按 `post_count` 加权均值或简单均值。
- 平台贡献解释：对每个 (symbol, platform) 计算平台分数并展示权重，支持“最近 N 天非零率”指标以衡量活跃度。
- 价格抓取：实现 `akshare` 优先抓取，失败时回退到东方财富或本地缓存（price_history_cache.csv）。
- 仪表盘：Streamlit 驱动的交互界面（`src/opinion_trading/ui_dashboard.py`），包含趋势图、平台雷达、选股解释卡、导出 CSV/PNG 等。

技术栈
- Python 3.12、pandas、Altair、Streamlit
- akshare（价格抓取首选）、本地 JSONL 数据作为 memory（data/memory）

常用路径
- 情感历史：data/memory/sentiment_history.jsonl
- 价格缓存：data/reports/price_history_cache.csv
- 导出报表：data/reports/
- 仪表盘入口：src/opinion_trading/ui_dashboard.py

快速运行（本地）
1. 创建并激活虚拟环境：

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. 启动 Streamlit 仪表盘：

   ```powershell
   streamlit run src/opinion_trading/ui_dashboard.py --server.port 8501
   ```

3. 页面打开后（默认中文）：
   - 在「情感趋势」区可以调整 `Min samples` 和 `Include zero scores`（默认已开启）。
   - 在「平台贡献」区设置 `Lookback days` 查看每个平台的非零率和样本数。

设计注意事项 / 备忘
- 前端图表（Altair/Vega-Lite）对数据类型敏感，所有类型转换与 fold/melt 在 pandas 层完成以避免前端类型推断问题。
- 原则上把 `0.0` 视为“无信号”，但界面允许将其视为有效以便展示像 Douyin 这类只有 0 分样例的平台。
- 平台贡献默认策略：每个 (symbol,platform) 取最近非空分数，再按绝对值加权计算权重。

下一步建议
- 将本简介合并到主 README，并补充英文版（README.md 双语）。
- 若需对外展示，生成一份简短的演示截图和导出样本（data/reports/agg_monthly_filtered.csv 与 PNG）。

维护者
- 仓库维护与开发：在本地仓库中查看 commits 与分支（例如 `feature/akshare-first`）。

文件位置
- 该简介已保存为 `docs/brief_intro_zh.md`。