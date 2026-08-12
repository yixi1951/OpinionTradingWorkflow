# Web 前端迁移说明

项目的正式用户入口已经从 Streamlit 切换为 `web/` 下的 React/Vite 单页应用。

## 本地启动

```powershell
copy .env.example .env
# 为 APP_SESSION_SECRET 设置随机值
$env:PYTHONPATH = "src"
cd web
npm install
npm run build
cd ..
python -m opinion_trading.services.api_app
```

打开 `http://localhost:8000`。前端和 API 使用同源地址，浏览器只接触 API 网关；采集、推理和计算服务只在 Docker Compose 内网暴露。

## Docker 启动

```powershell
copy .env.example .env
# 编辑 .env，至少设置 APP_SESSION_SECRET、GRAFANA_ADMIN_PASSWORD
docker compose up -d --build
```

镜像会在 Node 构建阶段生成 `web/dist`，再由 FastAPI 静态服务托管。旧的 `src/opinion_trading/ui_dashboard.py` 保留用于迁移期参考，但不再由 Compose 或 `scripts/run_ui.ps1` 启动。

## 当前前端范围

- 登录 / 注册 / 找回密码 / 重置密码页 / HttpOnly 会话
- 账户中心：邮箱验证重发、角色展示、admin RBAC、真实订单只读列表
- 研究总览：质量门禁、样本构成、最新信号、样本外评估
- 我的自选：添加、移除和最近信号
- 舆情证据：新闻与用户观点分开、原文链接和情绪分数
- 系统状态：API、采集、推理、计算服务健康

生产闸门与产品边界见 `docs/PRODUCTION_GATES.md`（舆情查询平台，不含实盘交易）。
