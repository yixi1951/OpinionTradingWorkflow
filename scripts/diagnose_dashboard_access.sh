#!/bin/bash
# Run on ECS as root: bash scripts/diagnose_dashboard_access.sh
set -euo pipefail

echo "========== 1. Streamlit process =========="
ps aux | grep -E 'streamlit|8501' | grep -v grep || echo "(no streamlit process)"

echo ""
echo "========== 2. Listen address (must be 0.0.0.0:8501 for public access) =========="
ss -tlnp 2>/dev/null | grep 8501 || netstat -tlnp 2>/dev/null | grep 8501 || echo "(nothing on 8501)"

echo ""
echo "========== 3. Local HTTP check =========="
curl -s -o /dev/null -w "127.0.0.1:8501 HTTP %{http_code}\n" --connect-timeout 3 http://127.0.0.1:8501 || echo "curl failed"

echo ""
echo "========== 4. Public IP of this host =========="
curl -s --connect-timeout 3 ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || hostname -I

echo ""
echo "========== 5. firewalld (if active) =========="
if command -v firewall-cmd &>/dev/null; then
  firewall-cmd --state 2>/dev/null || true
  firewall-cmd --list-ports 2>/dev/null || true
else
  echo "firewalld not installed"
fi

echo ""
echo "========== 6. iptables INPUT (8501) =========="
iptables -L INPUT -n 2>/dev/null | head -20 || echo "no iptables"

echo ""
echo "========== 7. BT panel firewalld file (if exists) =========="
if [ -f /www/server/panel/data/firewall.json ]; then
  grep -o '"8501[^"]*"' /www/server/panel/data/firewall.json 2>/dev/null | head -3 || true
else
  echo "no bt firewall.json"
fi

echo ""
echo "========== FIX HINTS =========="
echo "- Firewall source must be YOUR home public IP (search 我的公网IP), NOT 112.74.33.37"
echo "- Restart streamlit: --server.address 0.0.0.0 --server.port 8501"
echo "- If listen is 127.0.0.1:8501 only, public access will always fail"