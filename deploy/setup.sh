#!/usr/bin/env bash
# =============================================================================
# VPS Setup Script — yt-dlp YouTube Download API
# Run as root on Ubuntu/Debian VPS.
# =============================================================================
set -euo pipefail

APP_DIR=/opt/ytdlp-api
SERVICE=ytdlp-api
DOMAIN=ytdlp.gifted.co.ke
PORT=8888

echo "=== [1/8] System update & dependencies ==="
apt-get update -y
apt-get install -y python3 python3-pip python3-venv ffmpeg nginx curl git

echo "=== [2/8] Create app directory ==="
mkdir -p "$APP_DIR"
mkdir -p /var/log/ytdlp-api
mkdir -p /tmp/ytdlp_cache

echo "=== [3/8] Copy application files ==="
# (Files already rsynced by the deploy script before setup.sh runs)

echo "=== [4/8] Python virtual environment & packages ==="
cd "$APP_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# Install / upgrade yt-dlp separately to always get the latest
venv/bin/pip install --upgrade yt-dlp

echo "=== [5/8] yt-dlp version ==="
venv/bin/python -m yt_dlp --version

echo "=== [6/8] systemd service ==="
cp deploy/ytdlp-api.service /etc/systemd/system/${SERVICE}.service
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
sleep 2
systemctl status "$SERVICE" --no-pager || true

echo "=== [7/8] Nginx configuration ==="
cp deploy/nginx.conf /etc/nginx/sites-available/${DOMAIN}
ln -sf /etc/nginx/sites-available/${DOMAIN} /etc/nginx/sites-enabled/${DOMAIN}
# Remove default site if it's there
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

echo "=== [8/8] Health check ==="
sleep 3
curl -sf http://127.0.0.1:${PORT}/api/health && echo " — API is UP ✓" || echo " — WARNING: health check failed, check logs"

echo ""
echo "==================================================================="
echo "  API deployed at: http://${DOMAIN}"
echo "  Logs: journalctl -u ${SERVICE} -f"
echo "        /var/log/ytdlp-api/access.log"
echo "==================================================================="
