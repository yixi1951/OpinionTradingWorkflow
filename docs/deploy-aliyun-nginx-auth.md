# Nginx :80 反代 + 基础认证（OpenClaw 仪表盘）

解决 **移动网络封 8501**、**公网直连 Streamlit** 的问题：浏览器访问 **`http://你的公网IP/`**（80 端口），Nginx 反代到本机 `127.0.0.1:8501`，并加 **HTTP Basic Auth**。

## 前提

- `openclaw-dashboard.service` 已运行，且 **`--server.address 127.0.0.1 --server.port 8501`**（不要对公网直接暴露 8501）。
- 阿里云 / 宝塔防火墙放行 **TCP 80**（来源建议你的办公 IP 或临时 `0.0.0.0/0` 测通后收紧）。

## 1. 安装 Nginx

```bash
yum install -y nginx 2>/dev/null || dnf install -y nginx
systemctl enable nginx
```

## 2. 创建密码文件

```bash
chmod +x /opt/openclaw-picks/scripts/nginx_create_htpasswd.sh
bash /opt/openclaw-picks/scripts/nginx_create_htpasswd.sh /etc/nginx/openclaw.htpasswd admin
```

按提示输入密码（仅你本人知道）。

## 3. 启用站点配置

```bash
cp /opt/openclaw-picks/deploy/aliyun/nginx/openclaw-dashboard.conf /etc/nginx/conf.d/openclaw-dashboard.conf
nginx -t
systemctl reload nginx
```

若与宝塔默认 `default_server` 冲突，在宝塔里关掉占 80 的站点，或改 `openclaw-dashboard.conf` 的 `server_name` 为你的 IP/域名。

## 4. 访问

```text
http://112.74.33.37/
```

浏览器弹出用户名/密码：**admin** + 你在 htpasswd 里设的密码。

## 5. HTTPS（可选）

有域名时可用 **certbot** 或阿里云证书，在 Nginx 上增加 `listen 443 ssl` 与证书路径；Basic Auth 仍可保留。

## 6. 故障排查

| 现象 | 检查 |
|------|------|
| 502 Bad Gateway | `curl -I http://127.0.0.1:8501` 是否 200；`systemctl status openclaw-dashboard` |
| 401 一直要密码 | 正常；忘记密码则重新跑 `nginx_create_htpasswd.sh` |
| 仍打不开 80 | 安全组 + `ss -tlnp \| grep :80` |