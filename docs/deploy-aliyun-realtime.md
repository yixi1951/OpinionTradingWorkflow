# 阿里云 ECS 实时 AI 打分部署

在阿里云（或其他 Linux VPS）上跑 **OpenClaw Gateway → WS Proxy → opinion_trading realtime**，与本地 `scripts/restart_openclaw_deepseek.ps1` 架构一致。

## 架构

```
openclaw gateway (DeepSeek)  :18789 WS
        ↑
openclaw_ws_proxy (REST)     :18790  POST /api/v1/sentiment
        ↑
opinion_trading.main realtime / daily crawl + rescore
        ↓
data/reports, data/memory, data/raw  →  Streamlit UI
```

## 1. 准备 ECS

- 系统：Ubuntu 22.04+ / Alibaba Cloud Linux 3
- 规格建议：2 vCPU / 4 GiB+（Gateway + 爬虫 + Streamlit）
- 安全组：仅对办公 IP 开放 **8501**（Streamlit）；**18790/18789 仅本机**，不要公网暴露

```bash
sudo useradd -m -s /bin/bash openclaw || true
sudo mkdir -p /var/log/openclaw-picks
sudo chown openclaw:openclaw /var/log/openclaw-picks
```

## 2. 安装代码与依赖

```bash
sudo mkdir -p /opt/openclaw-picks
sudo chown openclaw:openclaw /opt/openclaw-picks
sudo -u openclaw git clone <your-repo> /opt/openclaw-picks
cd /opt/openclaw-picks
sudo -u openclaw python3 -m venv .venv
sudo -u openclaw .venv/bin/pip install -U pip
sudo -u openclaw .venv/bin/pip install -r requirements.txt
```

安装 **OpenClaw CLI** 与 `~/.openclaw/openclaw.json`（含 `gateway.auth.token`、`agents.defaults.model.primary`），与本地相同。

## 3. 环境变量

```bash
sudo cp deploy/aliyun/openclaw.env.example /etc/openclaw-picks.env
sudo chmod 600 /etc/openclaw-picks.env
sudo nano /etc/openclaw-picks.env
```

必改：

- `WS_GATEWAY_TOKEN` — 来自 `openclaw.json`
- `WS_GATEWAY_URL` / `OPENCLAW_URL` — 默认本机 18789 / 18790
- `OPENCLAW_PICKS_ROOT=/opt/openclaw-picks`

可选：

- `OPENCLAW_SKIP_ROW_SCORE=0` — 逐帖 LLM（慢，仅小批量 rescore 时用）
- `OPENCLAW_BATCH_SIZE=4` — 代理批量大小

## 4. systemd

```bash
sudo cp deploy/aliyun/systemd/*.service deploy/aliyun/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now openclaw-gateway.service
sudo systemctl enable --now openclaw-ws-proxy.service
sudo systemctl enable --now openclaw-realtime.timer
```

手动跑一次 realtime：

```bash
sudo systemctl start openclaw-realtime.service
tail -f /var/log/openclaw-picks/realtime.log
```

冒烟测试：

```bash
source /etc/openclaw-picks.env
curl -s -X POST "$OPENCLAW_URL/api/v1/sentiment" \
  -H 'Content-Type: application/json' \
  -d '{"texts":["业绩超预期，强烈看好","风险很大建议回避"]}'
```

## 5. Streamlit 仪表盘

```bash
sudo cp deploy/aliyun/systemd/openclaw-dashboard.service /etc/systemd/system/  # 若已提供
# 或 nohup:
sudo -u openclaw bash -lc 'set -a; source /etc/openclaw-picks.env; set +a; \
  cd /opt/openclaw-picks && .venv/bin/streamlit run src/opinion_trading/ui_dashboard.py \
  --server.address 0.0.0.0 --server.port 8501'
```

UI 侧边栏 **OpenClaw 状态** 绿点表示 `OPENCLAW_URL` 可达。

## 6. 日终 daily + OpenClaw 重打分（推荐 systemd timer）

```bash
cp /opt/openclaw-picks/deploy/aliyun/systemd/openclaw-daily-eod.* /etc/systemd/system/
chmod +x /opt/openclaw-picks/scripts/daily_eod_openclaw.sh
systemctl daemon-reload
systemctl enable --now openclaw-daily-eod.timer
systemctl list-timers openclaw-daily-eod.timer --no-pager
```

手动跑一轮：

```bash
systemctl start openclaw-daily-eod.service
tail -50 /var/log/openclaw-picks/daily_eod.log
```

环境变量（`/etc/openclaw-picks.env`）：`OPENCLAW_RESCORE_MAX_ROWS=120` 限制 2G 机器批量行数。

## 6b. Nginx :80 + 基础认证（公网访问 UI）

见 **[deploy-aliyun-nginx-auth.md](deploy-aliyun-nginx-auth.md)**。浏览器访问 `http://公网IP/`，无需 :8501。

## 7. 故障排查

| 现象 | 检查 |
|------|------|
| proxy 502 | `journalctl -u openclaw-gateway -n 50` |
| 打分超时 | 增大 `OPENCLAW_TIMEOUT`、`WS_GATEWAY_RESPONSE_TIMEOUT` |
| UI 无 picks | `data/reports/realtime_picks_*.csv` 是否更新；timer 是否 active |
| 全 keyword 分 | `OPENCLAW_URL` 未设或 gateway 未起 |

## 8. Windows 开发机（对照）

```powershell
.\scripts\restart_openclaw_deepseek.ps1
$env:OPENCLAW_SKIP_ROW_SCORE='1'
py -m opinion_trading.main --mode realtime --iterations 2 --interval-seconds 60
```