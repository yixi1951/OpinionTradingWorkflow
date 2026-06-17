# Contributing

Thanks for your interest in contributing!

## 开发环境 / Development Setup

```powershell
# 克隆 / Clone
git clone https://github.com/yixi1951/OpinionTradingWorkflow.git
cd OpinionTradingWorkflow

# 虚拟环境 / Virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖 / Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 安装 pre-commit 钩子（可选但推荐）
pre-commit install
```

## 代码规范 / Code Style

- **Linter**：`ruff check src tests`
- **Formatter**：`black --check --diff src tests`
- **Type check**：`mypy src/opinion_trading`
- 配置见 `pyproject.toml`（line-length=88）

提交前请确保以上检查通过。

## 测试 / Testing

```powershell
# 运行全部测试
pytest -q

# 带覆盖率
pytest --cov=src/opinion_trading --cov-report=term-missing

# 跳过慢测试
pytest -m "not slow"
```

- 所有新功能必须有单元测试
- Bug 修复应附带对应的回归测试
- 测试文件放在 `tests/` 目录，命名 `test_<模块名>.py`

## PR 流程 / Pull Request Workflow

1. Fork 仓库并创建特性分支
2. 确保 lint + type check + test 全部通过
3. 添加或更新相关文档（README、docs/）
4. 更新 `CHANGELOG.md` 记录变更
5. 创建 PR，描述变更内容和关联 Issue
6. 等待 CI 通过后进行 Review

## 提交信息 / Commit Messages

推荐 [Conventional Commits](https://www.conventionalcommits.org/) 风格：

```
feat: 添加 HTTP 缓存支持
fix: 修复股吧链接匹配漏采问题
test: 新增缓存过期测试
docs: 更新 README 配置说明
refactor: 收窄异常捕获类型
```

## 项目结构 / Project Structure

```
src/opinion_trading/
├── agents/          # 工作流编排（workflow）
├── core/            # 配置、存储、回测、日志、OpenClaw 适配器
├── integrations/    # 平台采集（真实 + Stub）
├── skills/          # 情感分析、交易模拟
├── main.py          # 入口
├── ui_dashboard.py  # Streamlit 仪表盘
└── ui_helpers.py    # UI 工具函数
scripts/             # 一键脚本、工具
tests/               # 测试
config/              # YAML 配置
```

## 问题报告 / Issue Reporting

请使用 GitHub Issues 并选择对应的模板（Bug Report / Feature Request）。
