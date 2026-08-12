# 已知局限与路线图

本文对照常见评审意见，说明**当前版本已缓解项**与**尚未实现项**，避免过度承诺。

## 一、官方已知局限（README 摘要）

| 局限 | 现状 | 缓解 / 计划 |
|------|------|----------------|
| 反爬 → fallback | 部分平台仍会出现 `capture_status=fallback` | 域名限速、`HTML` 磁盘缓存、`quality` 门控降置信 / 阻断；见 `REQUEST_MIN_INTERVAL` |
| 股吧等噪声 | 噪声率偏高 | `text_quality`、quality 报告、`data_quality` 门控 |
| 股票池小 | 默认 5 只样板 | 编辑 `config/settings.yaml` → `universe.symbols` |
| TF-IDF 基线 | 样本少，仅供参考 | 主路径为 **OpenClaw/关键词 hybrid** + 可选多 Agent；ML 基线非生产路径 |

## 二、数据采集与质量

| 评审点 | 已实现 | 未实现 / 长期 |
|--------|--------|----------------|
| 代理池 / 验证码 | 单 UA +  per-domain 限速 + 缓存 | 代理池、打码、登录态 |
| 知乎/B 站/小红书/公众号 | 6 平台（股吧/东财/新浪/微博/雪球/抖音） | 新平台需独立 adapter |
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
| **交易成本** | `simulation` 模式 `slippage_bps`；纸面 note 含价源 | 手续费模型写入回测 |
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
| 移动端 | Web 前端已提供紧凑布局 | 仍需真机可用性测试 |
| **认证** | Web 会话登录已接入 | 生产需接入正式用户中心与限流 |

## 七、安全

- API Key：**环境变量 / OpenClaw configure**，勿提交仓库。
- 仪表盘：**默认无登录**，勿公网暴露。

## 八、优先级路线图（P0–P4）

| 优先级 | 方向 | 本仓库已做 | 下一步 |
|--------|------|------------|--------|
| **P0** | 扩大股票池与 signal 历史、稳定 WF | `universe.symbols`；`--mode replay-batch` 按日 fast-daily 回放已有 raw CSV；`tests/fixtures` + CI smoke | 多日真实 raw 入库后批量 replay → `walk_forward` |
| **P1** | 样本外回测与纸面净值对齐 | Eval：信号评估 + WF 折表/CSV；**纸面净值曲线**（`paper_equity` + Eval Tab） | 净值与 `evaluate_signals` 同一价表校验 |
| **P2** | OpenClaw / 采集成功率 | 缓存、限速、并行采集日志、Hero fallback 告警 | 代理池、网关健康检查自动化 |
| **P3** | 人工标注 + ML 基线 | `docs/annotation_instructions_zh.md`、TF-IDF 训练路径 | 标注集 + 与 hybrid 对比报告 |
| **P4** | 合规与实盘 | `docs/broker_integration.md`、`execution` dry_run | 券商沙箱对接 |

**P0 命令示例**

```bash
# 每个交易日需有 data/raw/raw_posts_YYYY-MM-DD.csv
py -m opinion_trading.main --mode replay-batch --start-date 2026-06-01 --end-date 2026-06-17 --reset-paper
py -m opinion_trading.main --mode walk_forward --price-file data/reports/price_history_cache.csv
```

## 推荐答辩话术

1. 强调 **quality 门控 + walk-forward + 多 Agent 可解释**，而非单一 Sharpe。  
2. 承认 **免费采集与 LLM 延迟**，展示 **`--fast-daily`** 与纸面 **market 收盘价**。  
3. 实盘：**明确 dry_run + broker 适配器文档**，当前仅研究原型。
