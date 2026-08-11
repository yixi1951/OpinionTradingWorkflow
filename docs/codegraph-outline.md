# OpinionTradingWorkflow — CodeGraph 架构大纲

> 由 CodeGraph v0.9.9 索引生成（2026-06-07）  
> 索引统计：92 文件 · 1,087 符号 · 2,079 边 · 87 Python 文件

本文档是 AI 协作的**思考框架**：探索代码、规划改动、分析影响时，先对照此大纲定位模块，再用 CodeGraph MCP 工具深入。

---

## 1. 入口与启动

| 文件 | 职责 |
|------|------|
| `run_pipeline.py` | 项目根入口，注入 `src/` 到 path，调用 `main()` |
| `src/opinion_trading/main.py` | CLI 参数解析，按 `--mode` 分发 |
| `src/opinion_trading/ui_dashboard.py` | Streamlit 仪表盘（57 符号，最大 UI 模块） |
| `openclaw_ws_proxy.py` | OpenClaw WebSocket→HTTP 代理 |
| `openclaw_stub.py` | 无 Gateway 时的 LLM 桩实现 |

### CLI 模式（`main.py`）

| mode | 用途 |
|------|------|
| `daily` | 日度全流程 |
| `realtime` | 实时轮询选股 + 告警 |
| `train` | 月度训练 |
| `evaluate` | 模型评估 |
| `backtest` | 策略回测 |
| `optimize` | 参数优化 |
| `visualize` | 回测可视化 |

---

## 2. 核心编排 — `OpinionTradingWorkflow`

**路径**：`src/opinion_trading/agents/workflow.py`（25 符号）

### 依赖注入（`__init__`）

```
load_runtime_config
├── JsonLineMemoryStore      (data/memory)
├── RawPostCsvStore          (data/raw)
├── QualityReportBuilder     (data/reports)
├── RealPlatformSentimentProvider
├── AlertNotifier
└── Agent 三元组
    ├── CollectorAgent ← SentimentCollectionSkill
    ├── AnalystAgent   ← SentimentAnalysisSkill
    └── TraderAgent    ← PaperTradingSkill
```

### `run_daily()` 流水线

1. **采集** — 遍历 symbols × platforms，`provider.collect_raw_posts()`
2. **存储** — `raw_store.save_partitioned_rows()` + `save_failure_logs()`
3. **质检** — `quality_reporter.build()` → `quality_YYYY-MM-DD.md`
4. **日汇总** — `build_daily_summary()` → CSV + MD
5. **情感快照** — `collector.run()` → `sentiment_history.jsonl`
6. **信号生成** — `analyst.run()` → `signal_history.jsonl`
7. **模拟交易** — `trader.run()` → `trade_history.jsonl` + state 更新
8. **日报** — `reporter.build()` → `data/reports/YYYY-MM-DD.md`

### `run_realtime()` 流水线

1. 多轮轮询（`iterations` × `interval_seconds`）
2. 每轮：采集 → 聚合 → 信号 → Top-N 排名
3. 分数跳变检测 → 黄/橙/红分级告警 → `realtime_alerts.jsonl`
4. 输出 `realtime_picks_*.csv/md` + `realtime_pick_history.jsonl`

---

## 3. Agent 层

**路径**：`src/opinion_trading/agents/roles.py`（16 符号）

| Agent | Skill | 核心方法 |
|-------|-------|----------|
| `CollectorAgent` | `SentimentCollectionSkill` | `collect_for_days()` |
| `AnalystAgent` | `SentimentAnalysisSkill` | `aggregate()`, `generate_signals()` |
| `TraderAgent` | `PaperTradingSkill` | 模拟买卖执行 |

---

## 4. 技能层（`skills/`）

| 模块 | 类 | 职责 |
|------|-----|------|
| `sentiment_collection.py` | `SentimentCollectionSkill` | 按平台/股票/日期采集情感快照 |
| `sentiment_analysis.py` | `SentimentAnalysisSkill` | 多平台加权聚合、信号生成、组合质量评分 |
| `trade_simulation.py` | `PaperTradingSkill` | 纸面交易模拟 |

---

## 5. 平台集成（`integrations/`）

| 模块 | 类 | 职责 |
|------|-----|------|
| `platform_sentiment_real.py` | `RealPlatformSentimentProvider`（42 符号） | 6 平台真实 HTML 采集 + OpenClaw 打分 |
| `platform_sentiment_stub.py` | Stub 实现 | 演示/CI 兜底 |

支持平台（`config/settings.yaml`）：guba, sina_finance, weibo, eastmoney, xueqiu, douyin

---

## 6. 核心服务（`core/`）

| 模块 | 关键符号 | 职责 |
|------|----------|------|
| `openclaw_adapter.py` | `OpenClawClient` | LLM Gateway 情感打分适配 |
| `config_loader.py` | `load_runtime_config` | YAML 配置加载 |
| `models.py` | 数据模型 | OpinionSnapshot, TradeSignal, AggregatedSentiment 等 |
| `raw_store.py` | `RawPostCsvStore` | 原始帖按平台分区 CSV |
| `quality_report.py` | `QualityReportBuilder` | 标题/时间/正文覆盖率质检 |
| `memory_store.py` | `JsonLineMemoryStore` | JSONL 追加读写 + state.json |
| `daily_aggregator.py` | `build_daily_summary` | 日度汇总表 |
| `report_builder.py` | `DailyReportBuilder` | Markdown 日报 |
| `alert_notifier.py` | `AlertNotifier` | 实时告警推送 |
| `backtest.py` | `StrategyBacktester` | 策略回测 |
| `evaluation.py` | 评估工具 | 信号/价格加载与评估 |
| `monthly_training.py` | 训练管线 | 月度训练帧构建与报告 |
| `price_fetcher.py` | 行情获取 | akshare + 本地缓存 |
| `ai_sentiment.py` | AI 情感 | 备用情感分析 |
| `visualization.py` | 图表 | Sharpe vs threshold 等 |
| `metrics.py` | 指标 | 性能指标计算 |

---

## 7. UI 层

| 模块 | 符号数 | 职责 |
|------|--------|------|
| `ui_dashboard.py` | 57 | Streamlit 主页面：Top 排名、评论证据链、回测 |
| `ui_helpers.py` | 37 | 图表/表格/数据加载辅助 |

---

## 8. 脚本工具（`scripts/`，37 文件）

### 数据采集
- `crawl_guba_raw.py` — 股吧原始帖爬取 + `openclaw_score_rows()`
- `fetch_and_enrich.py` / `enrich_with_webtext.py` — 数据增强

### 标注与训练
- `auto_label_openclaw.py` — OpenClaw 自动标注
- `prepare_training.py` / `prepare_bulk_training.py` — 训练集准备
- `train_eval.py` / `train_baseline_fallback.py` — 模型训练评估
- `run_training_analysis.py` — 训练分析

### 运维与调试
- `rescore_raw_openclaw.py` — 原始数据重打分
- `text_quality.py` — 文本质量检测
- `ws_handshake.py` / `ws_probe.py` — Gateway 连通性探测
- `restart_openclaw_deepseek.ps1` — Windows 重启脚本

### 标注审核
- `label_review_app.py`（40 符号）— 标注审核 UI
- `sample_annotation.py` / `merge_labels.py` — 样本与合并

---

## 9. 配置与存储

### 配置
- `config/settings.yaml` — 策略阈值、平台权重、股票池
- `config/openclaw_tasks.yaml` — OpenClaw 任务定义

### 数据目录
```
data/
├── raw/          # 原始帖 CSV（按平台分区 by_source/）
├── memory/       # JSONL 历史（sentiment/signal/trade/realtime_*）
├── reports/      # 日报、选股、质量报告、训练报告
└── labels/       # 标注样本
```

---

## 10. 测试覆盖（`tests/`，13 文件）

| 测试文件 | 覆盖模块 |
|----------|----------|
| `test_main.py` | 入口导入 |
| `test_integration_realtime.py` | 实时流程集成 |
| `test_multi_source_sentiment.py` | 多平台情感 |
| `test_openclaw_adapter.py` | OpenClaw 适配器 |
| `test_core_backtest.py` | 回测 |
| `test_core_evaluation.py` | 评估 |
| `test_core_memory_store.py` | 内存存储 |
| `test_core_raw_store.py` | 原始存储 |
| `test_core_config_models.py` | 配置与模型 |
| `test_core_metrics.py` | 指标 |
| `test_text_quality.py` | 文本质量 |
| `test_ui_helpers.py` | UI 辅助 |

---

## 11. 改动前检查清单

1. **定位层级** — 改动属于入口/编排/Agent/集成/核心/脚本/UI 哪一层？
2. **查影响面** — `codegraph_impact <symbol>` 看上下游
3. **查调用链** — `codegraph_callers` / `codegraph_callees`
4. **对照测试** — `tests/` 中是否有对应覆盖？无则考虑补充
5. **数据流** — 是否影响 `data/raw` → `data/memory` → `data/reports` 链路？

---

## 12. 维护

```bash
# 重建索引（大幅重构后）
codegraph index

# 查看状态
codegraph status

# 搜索符号
codegraph query "符号名"
```

索引随文件保存自动同步（MCP 文件监视器，默认 2s 防抖）。
