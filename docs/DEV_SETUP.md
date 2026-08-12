# 开发环境（固定 venv）

答辩 / 协作时请**始终使用项目虚拟环境**，避免系统 Python 缺包导致「我机器能跑你机器不行」。

## Windows (PowerShell)

```powershell
cd C:\Users\ASUS\Desktop\project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest fastapi httpx
$env:PYTHONPATH = "src"
py -m pytest tests/ -q
```

## Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest fastapi httpx
export PYTHONPATH=src
python -m pytest tests/ -q
```

## 环境变量

复制 [`.env.example`](../.env.example) 为 `.env` 并按需填写（OpenClaw、采集并行、`APP_SESSION_SECRET` 等）。

终端采集进度条（需 `pip install tqdm`）：`COLLECT_SHOW_PROGRESS=1`

## Web 研究工作台

```powershell
$env:PYTHONPATH = "src"
cd web
npm install
npm run build
cd ..
python -m opinion_trading.services.api_app
```

浏览器访问 `http://localhost:8000`。正式入口是 `web/` 的同源前端，旧的
`ui_dashboard.py` 仅作为迁移期参考，不再作为部署入口。

## 常用命令

| 命令 | 说明 |
|------|------|
| `py -m opinion_trading.main --mode daily` | 日线 pipeline（信号、纸面、quality、event_log） |
| `py -m opinion_trading.main --mode daily --fast-daily --date YYYY-MM-DD` | 跳过爬虫，重放已有 raw CSV |
| `py -m opinion_trading.main --mode walk_forward` | 样本外 walk-forward 报告 |
| `py -m opinion_trading.main --mode evaluate` | 单次信号评估 |

`main.py` 与 API 启动时会自动加载项目根目录 **`.env`**（不覆盖已设置的环境变量）。

Docker：`docker compose up --build`（见根目录 `docker-compose.yml`）。

CI 配置见 [.github/workflows/ci.yml](../.github/workflows/ci.yml)。
