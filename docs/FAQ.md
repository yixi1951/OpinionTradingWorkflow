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
A: 否。`scoring.mode: keyword` 或 hybrid 在网关不可用时会回退关键词/Stub。可用 `python -m opinion_trading.main --mode gateway-health` 或 `scripts/check_gateway_health.py`：未配置 `OPENCLAW_URL` 时记 **HEALTH PASS [stub]**。

**Q: 如何用 DeepSeek 做真实情绪打分？**  
A: 设置 `DEEPSEEK_API_KEY`（可选 `DEEPSEEK_BASE_URL` 默认 `https://api.deepseek.com`，`DEEPSEEK_MODEL` 默认 `deepseek-chat`）。`config/settings.yaml` → `scoring.mode: ai`、`scoring.provider: deepseek`（密钥只走环境变量，不写 YAML）。本地：`python -m opinion_trading.main --mode deepseek-probe`；无 key 时 **NOT_CONFIGURED** 且 exit 2。`DEEPSEEK_REQUIRE=1` 时若请求了 live LLM 却缺 key 会抛明确中英错误；默认回退关键词。默认 CI（`.github/workflows/ci.yml`）使用 `SCORING_MODE=keyword`，不访问 DeepSeek。若 live 调用失败，会可选走 `QWEN_API_KEY` / `DASHSCOPE_API_KEY`（OpenAI 兼容），再回退关键词，并打一条 `LLM_FAILOVER` 警告。研究原型，不是收益承诺。

仓库里做一次真实探针（不把 key 发到聊天）：**Settings → Secrets and variables → Actions** 新建 secret，名称必须是 `DEEPSEEK_API_KEY`；然后 **Actions → DeepSeek probe → Run workflow**，选分支 `cursor/roadmap-p0-p5-7604`（工作流文件 `.github/workflows/deepseek-probe.yml`，仅手动触发）。

**Q: 代理池怎么配？**  
A: `config/settings.yaml` → `collection.proxy_urls` 或环境变量 `PROXY_POOL=url1,url2`。`ProxyRotator` 做 **round-robin + 失败跳过**，采集 GET 会带上 `proxies=`。质量探测：`python -m opinion_trading.main --mode proxy-health`（或 `scripts/check_proxy_health.py`）对每个代理发短 HTTP GET；**空池 skip/PASS**。**不做**验证码打码或登录态农场。未配置时直连。

## 数据与质量

**Q: fallback 行很多怎么办？**  
A: 看 `data/reports/quality_<date>.md` 与 UI 质量门控；调高 `quality.max_fallback_rate` 仅会放宽门控，不提高真实数据质量。长期需代理/登录态（见 [LIMITATIONS_AND_ROADMAP.md](LIMITATIONS_AND_ROADMAP.md)）。

**Q: 如何扩大股票池？**  
A: 编辑 `config/settings.yaml` → `universe.symbols`。

## 策略与回测

**Q: 准确率是否用了未来数据？**  
A: 评估使用信号日对应的 **下一交易日收益**（`next_return`）。若价表无重叠日期，会 `merge_asof` 并发出警告——答辩时应使用覆盖信号期的价 CSV。

**Q: 纸面净值为什么和评估指标对不上？**  
A: Eval Tab / CLI 与纸面 MTM 应读取同一收盘价表（`PRICE_FILE` 或 `data/reports/price_history_cache.csv`）。可用 `validate_paper_eval_price_alignment`；离线演示用 `tests/fixtures/price_history_replay.csv`。

## UI 与安全

**Q: 能否公网部署 Streamlit？**  
A: 设置环境变量 `STREAMLIT_DASHBOARD_PASSWORD=你的密码` 后，打开 UI 需输入密码（明文比对，适合演示；生产请 Nginx/OAuth）。

**Q: 如何一键导出报告？**  
A: 侧边栏 **「下载报告打包 (ZIP)」**，含 reports + memory 近期文件。

**Q: 如何导出选股结果？**  
A: `data/reports/realtime_picks_*.csv`、`daily_summary_*.csv`；纸面见 `data/memory/trade_history.jsonl`。