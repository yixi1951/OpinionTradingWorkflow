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

复制 [`.env.example`](../.env.example) 为 `.env` 并按需填写（DeepSeek、OpenClaw、采集并行、`STREAMLIT_DASHBOARD_PASSWORD` 等）。**不要提交 `.env` 或真实 API key。**

Live 情绪打分（DeepSeek 优先）：

```bash
cp .env.example .env   # 填入 DEEPSEEK_API_KEY=sk-...
export PYTHONPATH=src SCORING_MODE=ai
python -m opinion_trading.main --mode deepseek-probe
python -m opinion_trading.main --mode score-sample
# daily / pipeline 在 scoring.mode=ai 且 key 存在时走 DeepSeek；否则回退关键词
```

无 key 时探针打印 **NOT_CONFIGURED**（中英提示）。pytest / 默认 CI 删掉 `DEEPSEEK_API_KEY` 并 mock HTTP，不发起真实请求。

**GitHub Actions 真实探针（密钥只放仓库 Secret，不要贴到聊天里）**

1. Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
2. Name 必须是 **`DEEPSEEK_API_KEY`**，Value 填 DeepSeek 密钥
3. **Actions** → 工作流 **DeepSeek probe** → **Run workflow** → 选分支（例如 `cursor/roadmap-p0-p5-7604`）→ Run
4. 文件：`.github/workflows/deepseek-probe.yml`（仅 `workflow_dispatch`，不会在每次 PR push 跑）

终端采集进度条（需 `pip install tqdm`）：`COLLECT_SHOW_PROGRESS=1`

## Streamlit 仪表盘

Linux / macOS（推荐）：

```bash
bash scripts/run_ui.sh
# bash scripts/run_ui.sh --port 8502 --no-browser
# bash scripts/run_ui.sh --skip-demo   # 有数据时跳过 fast-daily
```

脚本会设置 `PYTHONPATH=src`，优先使用 `.venv`，默认 http://localhost:8501。无 `realtime_picks_*.md` 时会先跑一次 keyword `--fast-daily` 回放（可用 `--skip-demo` 关掉）。

Windows：

```powershell
$env:PYTHONPATH = "src"
powershell -ExecutionPolicy Bypass -File .\scripts\run_ui.ps1
# 或：streamlit run src/opinion_trading/ui_dashboard.py
```

### Docker Compose（一键 UI）

```bash
# Streamlit only — port 8501, mounts ./data and ./config
docker compose --profile ui up --build streamlit-ui
```

浏览器打开 http://localhost:8501。不要与全栈 `docker compose up` 同时跑（都会占用 8501）。

### 公网暴露前（演示级加固清单）

生产 OAuth / SSO 仍推迟；公网或团队共享环境建议至少：

1. **不要**把 `:8501` 直接暴露到互联网；用 Nginx（或云 LB）反代并启用 HTTPS。
2. 设置 **`STREAMLIT_DASHBOARD_PASSWORD`**（见 `.env.example`）；UI 内为明文比对，仅适合演示。
3. 可选：Nginx `auth_basic` 第二层（示例见 `deploy/nginx-streamlit.conf.example`）。
4. 防火墙仅放行 443；Streamlit 只监听 `127.0.0.1:8501`。
5. 密钥与 API Key 只走环境变量 / `.env`，勿写入 `config/settings.yaml` 或镜像层。
6. 完整 OAuth / 企业 SSO：**未实现**，见 `docs/LIMITATIONS_AND_ROADMAP.md`。

全栈（API :8000、collector :8001、inference :8002、compute :8003、dashboard :8501、Prometheus :9090、Grafana :3000）：

```bash
docker compose up --build
```

密钥走 `.env` / 环境变量，不要写进镜像。

## 常用命令

| 命令 | 说明 |
|------|------|
| `py -m opinion_trading.main --mode daily` | 日线 pipeline（信号、纸面、quality、event_log） |
| `py -m opinion_trading.main --mode daily --fast-daily --date YYYY-MM-DD` | 跳过爬虫，重放已有 raw CSV |
| `py -m opinion_trading.main --mode replay-batch --reset-paper` | P0：按 raw CSV 日期批量 fast-daily；无 raw 时 seed `tests/fixtures` |
| `py -m opinion_trading.main --mode walk_forward` | 样本外 walk-forward；价表走 `resolve_price_csv`（cache / fixture） |
| `python scripts/materialize_wf_history.py --dest /tmp/ot-honest-wf` | 生成 ~240 日 synthetic 价表+信号，供 3 折 60/20（不入库 raw） |
| `py -m opinion_trading.main --mode gateway-health` | P2：OpenClaw HTTP/WS 探针；无 URL 时 Stub PASS |
| `py -m opinion_trading.main --mode proxy-health` | P2：探测 `collection.proxy_urls` / `PROXY_POOL`；空池 skip/PASS |
| `python scripts/check_proxy_health.py` | 同上（脚本入口）；全部失败 exit 1 |
| `py -m opinion_trading.main --mode deepseek-probe` | DeepSeek 密钥探针；无 `DEEPSEEK_API_KEY` 时 `NOT_CONFIGURED`（exit 2，CI 不跑 live） |
| `py -m opinion_trading.main --mode score-sample` | 有 key 时对 3 条中文 fixture 做 live 打分（研究原型，非收益预测） |
| `python scripts/probe_deepseek.py` | 同上脚本入口；`--soft` 在未配置时 exit 0 |
| `python scripts/check_gateway_health.py --stub` | 同上（脚本入口） |
| `py -m opinion_trading.main --mode evaluate` | 单次信号评估（与纸面净值同一价表；可含滑点/费用；可选 `execution.transaction_costs`） |
| `python scripts/compare_ml_baseline.py --labels tests/fixtures/annotation_sample_labeled.csv` | P3：TF-IDF vs 关键词 vs offline hybrid（CI 无 key） |

Opt-in 采集平台（默认 daily 列表不含）：在 `config/settings.yaml` → `strategy.platforms` 取消注释 `zhihu` / `bilibili` / `xiaohongshu` / `weixin`。券商沙箱：`execution.mode: sandbox`（只记意图）。

`main.py` 与 Streamlit 启动时会自动加载项目根目录 **`.env`**（不覆盖已设置的环境变量）。

Docker：一键 UI 用 `docker compose --profile ui up --build streamlit-ui`（:8501）；全栈见根目录 `docker-compose.yml`。

CI 配置见 [.github/workflows/ci.yml](../.github/workflows/ci.yml)（离线）。真实 DeepSeek 探针见 [.github/workflows/deepseek-probe.yml](../.github/workflows/deepseek-probe.yml)（手动 **DeepSeek probe**）。