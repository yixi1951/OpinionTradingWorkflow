# 阿里云轻量 + 宝塔面板 · 一步一步部署 OpenClaw 实时打分

适用你的环境（示例）：

| 项 | 你的机器 |
|----|----------|
| 地域 | 华南1（深圳） |
| 公网 IP | `112.74.33.37` |
| 内网 IP | `172.17.44.62` |
| 系统 | 宝塔 Linux 面板 11.x |
| 规格 | 2 vCPU / 2 GiB / 40 GiB |

> **内存提示**：2 GiB 同时跑 Gateway + 爬虫 + Streamlit 会偏紧。下面会加 **2G swap**；日常建议 `OPENCLAW_SKIP_ROW_SCORE=1`，用定时 realtime + 关键词兜底，需要时再批量 rescore。

---

## 第 0 步：你要完成什么

1. 服务器上跑 **OpenClaw Gateway**（连 DeepSeek）  
2. 跑 **情感 REST 代理** `openclaw_ws_proxy`（`POST /api/v1/sentiment`）  
3. 定时跑 **realtime** 生成 Top3 选股与告警  
4. （可选）跑 **Streamlit 仪表盘**，浏览器访问  

---

## 第 1 步：登录服务器

### 方式 A：阿里云控制台（推荐第一次）

1. 打开截图里的实例卡片  
2. 点蓝色 **「远程连接」**  
3. 选 **Workbench / VNC**，用 root 或面板创建的用户登录  

### 方式 B：本机 SSH（Windows PowerShell）

```powershell
ssh root@112.74.33.37
```

首次会提示指纹，输入 `yes`。密码在阿里云 **重置密码** 或你自建密钥。

---

## 第 2 步：宝塔防火墙 + 阿里云安全组

### 2.1 宝塔面板

1. 浏览器打开 `http://112.74.33.37:8888`（端口以你面板为准）  
2. 登录宝塔 → **安全** → **防火墙**  
3. **放行**（仅你需要的）：  
   - `8501` — Streamlit（建议只对自家公网 IP 放行，不要 `0.0.0.0/0` 长期开放）  
   - `8888` — 面板（已有则不动）  
4. **不要**对公网放行 `18789`、`18790`（Gateway/代理只监听本机）

### 2.2 阿里云安全组

1. 控制台 → 轻量应用服务器 → 你的实例 → **防火墙 / 安全组**  
2. 添加入站规则：**TCP 8501**，来源填你的家庭/公司公网 IP  
3. 同样 **不要**开放 18789/18790 到公网  

---

## 第 3 步：安装系统依赖（SSH 里执行）

```bash
# 以 root 执行
apt update && apt install -y git python3 python3-venv python3-pip curl build-essential

# 2G 内存建议加 swap
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
free -h
```

---

## 第 4 步：创建运行用户与目录

```bash
useradd -m -s /bin/bash openclaw 2>/dev/null || true
mkdir -p /opt/openclaw-picks /var/log/openclaw-picks
chown -R openclaw:openclaw /opt/openclaw-picks /var/log/openclaw-picks
```

---

## 第 5 步：把项目代码弄到服务器

任选一种。

### 方式 A：Git（服务器能访问你的仓库时）

```bash
sudo -u openclaw git clone https://github.com/你的用户名/你的仓库.git /opt/openclaw-picks
```

### 方式 B：从你 Windows 电脑上传（无 Git 远程时）

在 **本机 PowerShell**（项目目录）：

```powershell
cd C:\Users\ASUS\Desktop\project
# 需已安装 scp（OpenSSH 客户端）
scp -r .\src .\config .\scripts .\deploy .\openclaw_ws_proxy.py .\requirements.txt `
  root@112.74.33.37:/opt/openclaw-picks/
ssh root@112.74.33.37 "chown -R openclaw:openclaw /opt/openclaw-picks"
```

上传后 SSH 到服务器补全结构：

```bash
ls -la /opt/openclaw-picks
# 应有 src/opinion_trading、openclaw_ws_proxy.py、requirements.txt、deploy/
```

---

## 第 6 步：Python 虚拟环境与依赖

```bash
cd /opt/openclaw-picks
sudo -u openclaw python3 -m venv .venv
sudo -u openclaw .venv/bin/pip install -U pip
sudo -u openclaw .venv/bin/pip install -r requirements.txt
```

验证：

```bash
sudo -u openclaw .venv/bin/python -c "import opinion_trading; print('ok')"
```

若报错 `No module named opinion_trading`：

```bash
echo 'export PYTHONPATH=/opt/openclaw-picks/src' >> /home/openclaw/.bashrc
```

---

## 第 7 步：安装 OpenClaw CLI + DeepSeek 配置

在服务器上用 **openclaw 用户**（或先 root 再 chown）：

```bash
# Node.js 18+（OpenClaw CLI 常见安装方式）
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
sudo -u openclaw bash -lc 'npm install -g openclaw@latest || true'
# 若官方包名不同，请与本地 Windows 安装方式对齐：
# 本地 PowerShell 里执行 where.exe openclaw 看路径与版本
```

创建配置目录：

```bash
sudo -u openclaw mkdir -p /home/openclaw/.openclaw
```

把 **你本机** 的 `C:\Users\ASUS\.openclaw\openclaw.json` 拷到服务器（PowerShell）：

```powershell
scp C:\Users\ASUS\.openclaw\openclaw.json openclaw@112.74.33.37:/home/openclaw/.openclaw/
```

SSH 检查（**不要**把 token 发到公开场合）：

```bash
sudo -u openclaw test -f /home/openclaw/.openclaw/openclaw.json && echo "config ok"
```

确认 JSON 里至少有：

- `gateway.auth.token`  
- `agents.defaults.model.primary`（如 `deepseek/deepseek-v4-flash`）  
- DeepSeek API Key 已按 OpenClaw 文档配置  

---

## 第 8 步：环境变量文件

```bash
cp /opt/openclaw-picks/deploy/aliyun/openclaw.env.example /etc/openclaw-picks.env
chmod 600 /etc/openclaw-picks.env
nano /etc/openclaw-picks.env
```

**必须修改**：

```bash
OPENCLAW_PICKS_ROOT=/opt/openclaw-picks
PYTHONPATH=/opt/openclaw-picks/src
OPENCLAW_URL=http://127.0.0.1:18790
WS_GATEWAY_URL=ws://127.0.0.1:18789
WS_GATEWAY_TOKEN=粘贴_openclaw.json_里的_gateway.auth.token_
```

**建议保持**（2G 机器）：

```bash
OPENCLAW_SKIP_ROW_SCORE=1
OPENCLAW_TIMEOUT=180
OPENCLAW_BATCH_SIZE=4
```

保存后：

```bash
chown root:root /etc/openclaw-picks.env
```

---

## 第 9 步：先手动试跑（确认再装 systemd）

### 9.1 终端 1 — Gateway

```bash
sudo -u openclaw bash -lc '
  set -a; source /etc/openclaw-picks.env; set +a
  export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/bin:$PATH"
  openclaw gateway run --port 18789 --force
'
```

看到监听 `18789`、无报错即可（Ctrl+C 先别关，下一步测完再关）。

若 `openclaw: command not found`，用 `which openclaw`（在 openclaw 用户下）把路径写进 systemd 或 `ln -s`。

### 9.2 终端 2 — WS 代理

```bash
sudo -u openclaw bash -lc '
  set -a; source /etc/openclaw-picks.env; set +a
  cd /opt/openclaw-picks
  .venv/bin/uvicorn openclaw_ws_proxy:app --host 127.0.0.1 --port 18790
'
```

### 9.3 终端 3 — 情感接口冒烟

```bash
curl -s -X POST http://127.0.0.1:18790/api/v1/sentiment \
  -H "Content-Type: application/json" \
  -d "{\"texts\":[\"业绩超预期强烈看好\",\"利空暴跌风险很大\"]}"
```

期望：`{"scores":[正数,负数]}` 或类似 JSON。  
若超时：等 Gateway 完全起来后再试，或加大 `WS_GATEWAY_RESPONSE_TIMEOUT`。

### 9.4 跑一次 realtime

```bash
sudo -u openclaw bash -lc '
  set -a; source /etc/openclaw-picks.env; set +a
  cd /opt/openclaw-picks
  .venv/bin/python -m opinion_trading.main --mode realtime \
    --iterations 2 --interval-seconds 60 --top-n 3
'
```

检查输出：

```bash
ls -lt /opt/openclaw-picks/data/reports/realtime_picks_* | head -3
```

手动试跑成功后，Ctrl+C 停掉两个前台进程，进入第 10 步用 systemd 常驻。

---

## 第 10 步：systemd 开机自启

```bash
cp /opt/openclaw-picks/deploy/aliyun/systemd/*.service /etc/systemd/system/
cp /opt/openclaw-picks/deploy/aliyun/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload

systemctl enable openclaw-gateway.service
systemctl enable openclaw-ws-proxy.service
systemctl enable openclaw-realtime.timer
systemctl enable openclaw-dashboard.service   # 可选

systemctl start openclaw-gateway.service
sleep 5
systemctl start openclaw-ws-proxy.service
systemctl start openclaw-realtime.service    # 立即跑一轮
systemctl start openclaw-dashboard.service   # 可选
```

查看状态：

```bash
systemctl status openclaw-gateway openclaw-ws-proxy openclaw-realtime.timer --no-pager
journalctl -u openclaw-ws-proxy -n 30 --no-pager
tail -n 50 /var/log/openclaw-picks/realtime.log
```

定时器（工作日 9–15 点每 30 分钟）：

```bash
systemctl list-timers | grep openclaw
```

---

## 第 11 步：浏览器打开仪表盘

本机浏览器（需第 2 步已放行 **你的 IP → 8501**）：

```text
http://112.74.33.37:8501
```

侧边栏 **OpenClaw** 应为绿色 **已连接**。  
主题可切 **深色**；**评论依据** 里选股票可看 **单股情感卡片**。

### 用宝塔反向代理（可选，更安全）

1. 宝塔 → **网站** → 添加站点（或用子域名）  
2. **反向代理** → 目标 `http://127.0.0.1:8501`  
3. 配置 SSL（Let’s Encrypt）  
4. 安全组只开放 **443**，关闭公网 8501  

Streamlit 需加启动参数（改 `openclaw-dashboard.service`）：

```ini
ExecStart=... streamlit run src/opinion_trading/ui_dashboard.py \
  --server.address 127.0.0.1 --server.port 8501 \
  --server.enableCORS false --server.enableXsrfProtection true
```

---

## 第 12 步：日更爬虫（可选，工作日收盘后）

```bash
crontab -u openclaw -e
```

加入：

```cron
30 18 * * 1-5 bash -lc 'set -a; source /etc/openclaw-picks.env; set +a; cd /opt/openclaw-picks && .venv/bin/python -m opinion_trading.main --mode daily' >> /var/log/openclaw-picks/daily.log 2>&1
```

---

## 常见问题

| 现象 | 处理 |
|------|------|
| `openclaw: not found` | `sudo -u openclaw npm list -g`；把可执行路径写入 `openclaw-gateway.service` 的 `ExecStart` |
| curl 情感 502/504 | `journalctl -u openclaw-gateway -n 50`；检查 token、DeepSeek 额度 |
| realtime 无 CSV | 看 `realtime.err.log`；是否爬虫被墙/超时 |
| 内存 OOM | 确认 swap；关掉 dashboard 或降低 `--iterations` |
| UI 连不上 | 安全组/宝塔是否放行 8501；`ss -lntp | grep 8501` |

---

## 和你本机 Windows 对照

| 本机 | 服务器 |
|------|--------|
| `restart_openclaw_deepseek.ps1` | `openclaw-gateway` + `openclaw-ws-proxy` systemd |
| `$env:OPENCLAW_URL` | `/etc/openclaw-picks.env` |
| `streamlit run ui_dashboard.py` | `openclaw-dashboard.service` |
| 手动 realtime | `openclaw-realtime.timer` |

本机开发、服务器跑定时任务时，只要把 `data/reports` 同步下来也能在本地 UI 看结果（`scp` 或网盘）。

---

## 检查清单（打勾即用）

- [ ] 能 SSH 登录 `112.74.33.37`  
- [ ] 代码在 `/opt/openclaw-picks`  
- [ ] `.venv` + `pip install -r requirements.txt` 成功  
- [ ] `/home/openclaw/.openclaw/openclaw.json` 已就位  
- [ ] `/etc/openclaw-picks.env` 中 `WS_GATEWAY_TOKEN` 已填  
- [ ] `curl` 情感接口返回 scores  
- [ ] `realtime` 生成 `data/reports/realtime_picks_*.csv`  
- [ ] systemd 三个服务 + timer `active`  
- [ ] 浏览器能打开仪表盘且 OpenClaw 绿点  

完成以上即 **阿里云实时 AI 打分** 上线。若某一步报错，把 **完整命令 + 终端输出**（打码 token）发出来可继续排查。