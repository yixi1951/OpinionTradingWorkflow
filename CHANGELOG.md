# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 新增
- HTTP 磁盘缓存（`HTML_CACHE_DIR` / `HTML_CACHE_TTL_SECONDS`）避免重复请求
- 每域名请求速率限制（`REQUEST_MIN_INTERVAL` + 随机抖动）
- 集中式日志配置 `log_utils.py`：支持文件输出、`RotatingFileHandler` 轮转
- OpenClaw WS 代理 `/health` 健康检查端点
- 网关看门狗脚本 `scripts/gateway_watchdog.ps1`
- 数据行模式验证 `validate_row_schema()` 在保存时告警
- `run_pipeline.py` 优雅关闭：SIGTERM/SIGINT 信号处理器
- `config/settings.yaml` 新增 `scoring` 节（`mode` / `row_level_llm` / `max_posts`）
- 评分模式配置：`keyword` / `openclaw` / `hybrid`（默认）
- Dockerfile 新增 `HEALTHCHECK` 和端口 18790 暴露
- pre-commit 配置（ruff、black、mypy、标准钩子）
- CI 新增覆盖率阈值检查（fail-under=44）和报告上传
- 项目基础设施：`.editorconfig`、`.gitattributes`、Issue/PR 模板、`SECURITY.md`

### 改进
- 所有 `print()` 替换为 `logging` 结构化日志
- `except` 语句收窄：仅捕获已知异常类型而非通用 Exception
- OpenClaw 回退告警：API 失败或返回数量不匹配时记录警告
- `pyproject.toml` 新增 pytest/coverage 配置、项目元数据
- `README.md` 新增徽章行、质量指标表、项目状态
- 测试从 58 增长到 113 个，覆盖日志、缓存、限速、模式验证、适配器等

### 修复
- 修复 `collect_raw_posts()` 的异常处理泄漏问题
- 修复股吧文章链接匹配不全导致的漏采
- 修复新闻标题缺少"纳斯达克100指数期货"等识别关键词
- 修复 AI 情感分析在 OpenClaw 网关运行时的测试路径错误

### 依赖
- 新增 `pydantic==2.11.3`、`websockets>=10.0`

### 2026-05-31

- Add fallback price-matching behavior when signal dates do not directly overlap price dates: use per-symbol `merge_asof` to match signals to the nearest prior available price and compute next-day returns where possible.
- Ensure merged evaluation frame has a canonical `symbol` column after merges and drop temporary `symbol_x`/`symbol_y` columns.
- Avoid matching to terminal price rows without a computable `next_return` (drop such rows before asof matching).
- Emit a `UserWarning` when fallback matching is used so runs are observable in logs.
- This fixes training runs that previously produced zero monthly rows when local price CSVs lacked signal-date coverage.
