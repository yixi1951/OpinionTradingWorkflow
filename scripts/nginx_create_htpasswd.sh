#!/usr/bin/env bash
# Create /etc/nginx/openclaw.htpasswd for dashboard basic auth (run as root on ECS).
set -euo pipefail

OUT="${1:-/etc/nginx/openclaw.htpasswd}"
USER="${2:-admin}"

if ! command -v htpasswd &>/dev/null; then
  echo "Installing httpd-tools..."
  yum install -y httpd-tools 2>/dev/null || dnf install -y httpd-tools
fi

mkdir -p "$(dirname "$OUT")"
if [[ -f "$OUT" ]]; then
  htpasswd "$OUT" "$USER"
else
  htpasswd -c "$OUT" "$USER"
fi
chmod 640 "$OUT"
chown root:nginx "$OUT" 2>/dev/null || chown root:root "$OUT"
echo "Wrote $OUT (user=$USER). Reload nginx: nginx -t && systemctl reload nginx"