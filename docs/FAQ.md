# 常见问题 (FAQ)

## 安装与运行

**Q: `ModuleNotFoundError: No module named 'fastapi'`**  
A: 使用项目 venv：`pip install -r requirements.txt pytest fastapi httpx`，并设置 `PYTHONPATH=src`。见 [DEV_SETUP.md](DEV_SETUP.md)。

**Q: daily 跑很久 / 卡住**  
A: 正常：6 平台 × N 股票 × 网络采集 + 可选 OpenClaw。答辩可用：  
`py src/opinion_trading/main.py --mode daily --date 2026-06-17 --fast-daily`（需已有 `data/raw/raw_posts_<date>.csv`）。

**Q: 采集进度怎么看？**  
A: 并行采集会写 `data/reports/collect_progress_<date>.jsonl`（每任务一行）。终端可设 `COLLECT_SHOW_PROGRESS=1` 显示 tqdm（需 `pip install tqdm`）。

**Q: Eval Tab walk-forward 折线表？**  
A: 有价表 + `signal_history.jsonl` 时进入 **Eval** 会自动跑 WF 并生成 `walk_forward_report.json`，界面展示各折训练/测试准确率表；也可点按钮重跑。

**Q: OpenClaw 必须装吗？**  
A: 否。`scoring.mode: keyword` 或 hybrid 在网关不可用时会回退关键词/Stub。

## 数据与质量

**Q: fallback 行很多怎么办？**  
A: 看 `data/reports/quality_<date>.md` 与 UI 质量门控；调高 `quality.max_fallback_rate` 仅会放宽门控，不提高真实数据质量。长期需代理/登录态（见 [LIMITATIONS_AND_ROADMAP.md](LIMITATIONS_AND_ROADMAP.md)）。

**Q: 如何扩大股票池？**  
A: 编辑 `config/settings.yaml` → `universe.symbols`。

## 策略与回测

**Q: 准确率是否用了未来数据？**  
A: 评估使用信号日对应的 **下一交易日收益**（`next_return`）。若价表无重叠日期，会 `merge_asof` 并发出警告——答辩时应使用覆盖信号期的价 CSV。

**Q: 和 walk-forward 区别？**  
A: 单次 evaluate 可能是全样本；`walk_forward` / Eval Tab 滚动 train/test 看**样本外**落差。

## UI 与安全

**Q: 能否公网部署 Streamlit？**  
A: 设置环境变量 `STREAMLIT_DASHBOARD_PASSWORD=你的密码` 后，打开 UI 需输入密码（明文比对，适合演示；生产请 Nginx/OAuth）。

**Q: 如何一键导出报告？**  
A: 侧边栏 **「下载报告打包 (ZIP)」**，含 reports + memory 近期文件。

**Q: 如何导出选股结果？**  
A: `data/reports/realtime_picks_*.csv`、`daily_summary_*.csv`；纸面见 `data/memory/trade_history.jsonl`。