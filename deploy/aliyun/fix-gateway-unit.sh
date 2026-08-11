#!/bin/bash
# Run on ECS as root: bash /opt/openclaw-picks/deploy/aliyun/fix-gateway-unit.sh
set -euo pipefail

cat > /etc/systemd/system/openclaw-gateway.service << 'EOF'
[Unit]
Description=OpenClaw gateway
After=network.target

[Service]
Type=simple
User=openclaw
Group=openclaw
Environment=HOME=/home/openclaw
Environment=PATH=/usr/bin:/usr/local/bin
EnvironmentFile=-/etc/openclaw-picks.env
WorkingDirectory=/home/openclaw
ExecStart=/usr/bin/openclaw gateway run --port 18789 --force
Restart=on-failure
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sed -i 's/\r$//' /etc/systemd/system/openclaw-gateway.service
systemctl daemon-reload
systemctl restart openclaw-gateway
sleep 10
systemctl status openclaw-gateway --no-pager || true
ss -tlnp | grep 18789 || echo "WARN: still no 18789 listener — check journalctl -u openclaw-gateway -n 50"