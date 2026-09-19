# 已知局限与路线图

本文对照常见评审意见，说明**当前版本已缓解项**与**尚未实现项**，避免过度承诺。

## 一、官方已知局限（README 摘要）

| 局限 | 现状 | 缓解 / 计划 |
|------|------|----------------|
| 反爬 → fallback | 部分平台仍会出现 `capture_status=fallback` | 域名限速、`HTML` 磁盘缓存、`quality` 门控降置信 / 阻断；见 `REQUEST_MIN_INTERVAL` |
| 股吧等噪声 | 噪声率偏高 | `text_quality`、quality 报告、`data_quality` 门控 |
| 股票池小 | 默认沪深300流动子集（约 17 只样板） | 编辑 `config/settings.yaml` → `universe.symbols`；`--mode sync_universe` |
| TF-IDF 基线 | 离线 n-gram 质心 + 与关键词对比报告 | 主路径为 **OpenClaw/关键词 hybrid** + 可选多 Agent；ML 基线非生产路径 |

## 二、数据采集与质量

| 评审点 | 已实现 | 未实现 / 长期 |
|--------|--------|----------------|
| 代理池 / 验证码 | 单 UA + per-domain 限速 + 缓存；**gateway health** CLI；`collection.proxy_urls` / `PROXY_POOL` + **`ProxyRotator` round-robin / 失败跳过** | 生产级代理质量探测、打码、登录态农场 |
| 知乎/B 站/小红书/公众号 | 6 默认平台 + **知乎 / B 站 / 小红书 / 公众号** best-effort HTML adapter（均默认不加入 daily 爬取列表） | 登录墙 / 验证码后的稳定抓取；互动字段 |
| 评论/点赞/转发 | 帖子标题+正文为主 | 互动字段与热度权重 |
| **去重** | `text_dedup.dedupe_raw_rows`（daily 采集后） | 跨日全局 dedup DB |
| 水军识别 | 噪声规则 + quality 统计 | 账号图谱 / 行为模型 |
| 时间校准 | 多格式 regex + trade_date 补年 | 统一 UTC 时区库 |
| 极端情感值 | quality 门控 + 阈值策略 | 分位数 Winsorize |

## 三、LLM 与策略

| 评审点 | 已实现 | 未实现 |
|--------|--------|--------|
| 备用 LLM | `scoring.mode: keyword` 离线；Stub 兜底 | 多厂商 API 自动切换 |
| 情绪细分 | 单维 score | 多标签情绪 |
| 时效权重 | **daily + realtime** `sentiment_recency` 半衰期加权；实时 delta 告警 | 跨平台统一 UTC |
| 反讽/黑话 | LLM + 关键词 | 领域微调 |
| **多因子** | Multi-Agent：情绪+技术+基本面+共识 | 行业/宏观因子 |
| **风控** | `risk_controls`、Kelly 上限、纸面市价 | 止盈止损、实盘 |
| **交易成本** | `execution.simulation_slippage_bps` / `fee_bps` 写入 **evaluate_signals 策略收益** 与纸面成交价（同一价表路径） | 券商佣金档位 / 印花税日历 |
| 实时 9 分钟 | `row_level_llm: false` 默认；`--fast-daily` 演示 | 并行 LLM / 批处理 |

## 四、回测与过拟合

| 评审点 | 已实现 | 说明 |
|--------|--------|------|
| 前视偏差 | 信号用 **T+1 `next_return`**，报告注明 merge_asof 回退 | 见 `evaluate_signals` 与评估 MD 脚注 |
| 样本外 | **`walk_forward`** CLI + Eval Tab UI | 需足够 `signal_history.jsonl` |
| 指标 | 准确率、Sharpe-like、**最大回撤、盈亏比、Profit factor、Calmar-like** | UI 与 CLI 已输出扩展指标 |

## 五、架构与工程

| 评审点 | 现状 |
|--------|------|
| 串行 pipeline | daily 串行；适合个人项目 |
| 分布式 | 未做 |
| 存储 | JSONL/CSV + Parquet 行情缓存；`event_log.jsonl` 审计 |
| 监控告警 | 日志 + realtime 告警 JSONL；无 Prometheus |
| **测试** | pytest **120+**；CI GitHub Actions |

## 六、部署与 UX

| 评审点 | 已实现 | 计划 |
|--------|--------|------|
| 仅 Windows 脚本 | **`docs/DEV_SETUP.md`** + bash 等价命令 | `scripts/run_ui.sh` |
| 容器 | `Dockerfile` | **`docker-compose.yml`** 一键 UI |
| UI 参数 | 侧边栏目录、Eval 价源 | 侧边栏改 `settings` 只读预览 |
| 导出 | reports CSV/MD、execution intents | UI 一键下载 zip |
| 移动端 | Streamlit 响应式一般 | 未专门适配 |
| **认证** | 无（本地演示） | `STREAMLIT_PASSWORD` / 反代 |

## 七、安全

- API Key：**环境变量 / OpenClaw configure**，勿提交仓库。
- 仪表盘：**默认无登录**，勿公网暴露。

## 八、优先级路线图（P0–P4）

| 优先级 | 方向 | 本仓库已做 | 下一步 |
|--------|------|------------|--------|
| **P0** | 扩大股票池与 signal 历史、稳定 WF | `universe.symbols`（约 17 只）；`--mode replay-batch` 在 **无多日 raw CSV 时自动 seed `tests/fixtures/raw_posts_YYYY-MM-DD.csv`** 并 **按 weekday 扩展至 2026-03-23..2026-06-17（~87 日）**；默认 60/20 窗口在该 span 上不再收缩；**3 折 60/20** 用 `scripts/materialize_wf_history.py` 在 tmp 生成 ~240 日 synthetic 价表+信号（不入库 170+ raw CSV） | 更长**真实** raw / 价表入库后才能替代 synthetic 3 折 |
| **P1** | 样本外回测与纸面净值对齐 | Eval：信号评估 + WF 折表/CSV；**纸面净值曲线** 与 `evaluate_signals` **共用同一收盘价表**；可选 `slippage_bps`/`fee_bps` | 真实券商沙箱 API（当前仅 stub） |
| **P2** | OpenClaw / 采集成功率 | 缓存、限速、并行采集日志；**`scripts/check_gateway_health.py` / `--mode gateway-health`**（无 URL 时 Stub PASS）；`ProxyRotator` 轮换 `collection.proxy_urls` / `PROXY_POOL` | 验证码打码、登录态、代理质量探测 |
| **P3** | 人工标注 + ML 基线 | `docs/annotation_instructions_zh.md`、`scripts/sample_annotation.py`（含 `label_source`/`annotator`）、`scripts/compare_ml_baseline.py`（TF-IDF vs 关键词 vs **offline hybrid**；36 行平衡 **synthetic** fixture）；`scripts/train_eval.py` sklearn 可选；live hybrid 需 `HYBRID_USE_LLM=1` + key | 更大**人工**标注 + 有 key 时 hybrid LLM |
| **P4** | 合规与实盘 | `docs/broker_integration.md`、`execution` dry_run；纸面滑点/费用；**`SandboxBrokerAdapter` 只记意图、不下单** | 真实券商 REST/FIX / 资金账户 |

**P0 命令示例（无真实 raw 时也会从 `tests/fixtures` seed 多日 CSV + 价表）**

```bash
export PYTHONPATH=src OPENCLAW_SKIP_ROW_SCORE=1 SCORING_MODE=keyword
# 省略 --start-date/--end-date 时回放 raw_dir 中全部日期（含 seed 的 fixture 日）
python -m opinion_trading.main --mode replay-batch --reset-paper
python -m opinion_trading.main --mode walk_forward --price-file tests/fixtures/price_history_replay.csv
```

指定区间（有真实 raw 时）：

```bash
python -m opinion_trading.main --mode replay-batch --start-date 2026-06-11 --end-date 2026-06-17 --reset-paper
python -m opinion_trading.main --mode walk_forward --price-file data/reports/price_history_cache.csv
```

`--start-date` / `--end-date` 的 2025 默认值仅用于 **backtest/optimize**；replay-batch 省略日期时不再误过滤掉 2026 fixture。

Fixture 日历跨度约 **2026-03-23 → 2026-06-17（~87 日）**：足够 **不收缩** 默认 60/20 窗口跑出至少一折。三个互不重叠的 60/20 折（约 240 日历日）用 **生成式 fixture**，不把 170+ raw CSV 提交进仓库：

```bash
PYTHONPATH=src python scripts/materialize_wf_history.py --dest /tmp/ot-honest-wf
python -m opinion_trading.main --mode walk_forward \
  --price-file /tmp/ot-honest-wf/price_history_honest_wf.csv
```

该 bundle 是 **synthetic** 价表 + 信号；与真实采集历史仍有差距。`--include-raw` 才会在 tmp 克隆 weekday raw CSV。

**P1 价表对齐**

- `evaluate_signals` 与纸面 MTM 都通过 `lookup_close` / `market_data` 本地价表读取同一 CSV（优先 `PRICE_FILE`，否则 `data/reports/price_history_cache.csv`，再否则 `tests/fixtures/price_history_replay.csv`）。
- 校验：`validate_paper_eval_price_alignment(price_df, memory_dir)`（pytest 覆盖）。

**P3 ML 基线（离线 smoke）**

```bash
PYTHONPATH=src python scripts/sample_annotation.py \
  --infile tests/fixtures/raw_posts_smoke_min.csv --n 8 --out data/labels/annotation_sample.csv
PYTHONPATH=src python scripts/compare_ml_baseline.py \
  --labels tests/fixtures/annotation_sample_labeled.csv \
  --out data/reports/ml_baseline_comparison.md
```

报告为研究对照，**不是**实盘收益承诺。sklearn 路径（可选）：

```bash
# 需 pip install scikit-learn joblib；CI 无此包时单测 skip
PYTHONPATH=src python scripts/train_eval.py \
  --labels tests/fixtures/annotation_sample_labeled.csv \
  --out_dir /tmp/ot-models --test_size 0.34 --n-estimators 8
```

**P2 网关健康检查**

```bash
# 无 OPENCLAW_URL：Stub PASS（离线/CI）
PYTHONPATH=src python scripts/check_gateway_health.py --stub
# 或
python -m opinion_trading.main --mode gateway-health
# 有网关：
OPENCLAW_URL=http://127.0.0.1:18790 PYTHONPATH=src python scripts/check_gateway_health.py
```

`collection.proxy_urls` / `PROXY_POOL` 由 `ProxyRotator` 做 round-robin / 失败跳过，采集 GET 带 `proxies=`。**仍不**做验证码打码、登录 cookie 农场或代理健康探测（可选后续）。

**P5 知乎 / B 站 / 小红书 / 公众号 adapter**

- `RealPlatformSentimentProvider` 支持 `zhihu`、`bilibili`、`xiaohongshu`（别名 `xhs`）、`weixin`（别名 `gongzhonghao` / `wechat_oa`）：搜索/列表页 HTML + stub fallback。
- 默认 `strategy.platforms` **不**包含上述四者，避免 daily 强制外网；需要时在 `config/settings.yaml` 取消注释对应行。
- 单测使用 `tests/fixtures/zhihu_page.html`、`bilibili_page.html`、`xiaohongshu_page.html`、`weixin_page.html`。
- 公众号真实 mp 页常被登录墙拦截，CI 以 fixture + stub 为准。

**交易成本（P1/P4-adjacent）**

- `evaluate_signals(..., slippage_bps=, fee_bps=)` 从策略收益中扣除单边成本；纸面成交价 `apply_fill_price` 对 BUY 上浮、SELL 下调。
- 默认 `execution.simulation_slippage_bps: 5`，`fee_bps: 0`。MTM 仍用中间价（价表 close）。
- **券商沙箱 stub 已落地**（`SandboxBrokerAdapter` 只记 dry-run 意图）；真实柜台 API 仍未实现（见 `docs/broker_integration.md`）。

## 推荐答辩话术

1. 强调 **quality 门控 + walk-forward + 多 Agent 可解释**，而非单一 Sharpe。  
2. 承认 **免费采集与 LLM 延迟**，展示 **`--fast-daily`** 与纸面 **market 收盘价**。  
3. 实盘：**明确 dry_run + broker 适配器文档**，当前仅研究原型。