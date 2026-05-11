#!/usr/bin/env bash
# =============================================================================
# File Processor API — One-click deployment script
# Tested on: Ubuntu 22.04 LTS
# Usage:     sudo bash deploy.sh
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${BLUE}→${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }
header() { echo -e "\n${BOLD}${BLUE}── $1 ──${NC}"; }

# ── Config ───────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/avsk-net/file-processor-api.git"
APP_DIR="/opt/file_processor_api"
APP_USER="root"
APP_PORT="8002"
NGINX_PORT="8080"

# ── Root check ───────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && fail "Run as root: sudo bash deploy.sh"

# ── Banner ───────────────────────────────────────────────────────────────────
echo -e "${BOLD}"
echo "  ███████╗██╗██╗     ███████╗    ██████╗ ██████╗  ██████╗  ██████╗"
echo "  ██╔════╝██║██║     ██╔════╝    ██╔══██╗██╔══██╗██╔═══██╗██╔════╝"
echo "  █████╗  ██║██║     █████╗      ██████╔╝██████╔╝██║   ██║██║     "
echo "  ██╔══╝  ██║██║     ██╔══╝      ██╔═══╝ ██╔══██╗██║   ██║██║     "
echo "  ██║     ██║███████╗███████╗    ██║     ██║  ██║╚██████╔╝╚██████╗"
echo "  ╚═╝     ╚═╝╚══════╝╚══════╝    ╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚═════╝"
echo -e "${NC}"
echo -e "  ${BOLD}File Processor API — One-click deployment${NC}"
echo -e "  ${BLUE}github.com/avsk-net/file-processor-api${NC}\n"

# ── Gather config ─────────────────────────────────────────────────────────────
header "Configuration"

read -rp "  Domain name (leave blank to use server IP only): " DOMAIN
read -rp "  Set up HTTPS with Let's Encrypt? (y/n, requires domain): " SETUP_HTTPS
read -rp "  File expiry in hours [24]: " FILE_EXPIRY
FILE_EXPIRY=${FILE_EXPIRY:-24}

SERVER_NAME="${DOMAIN:-_}"
echo ""

# ── Step 1: System packages ──────────────────────────────────────────────────
header "Step 1/8 — Installing system packages"
apt-get update -qq
apt-get install -y -qq \
    python3.10 python3.10-venv python3-pip \
    redis-server nginx git curl \
    > /dev/null 2>&1
ok "System packages installed"

if [[ "$SETUP_HTTPS" == "y" && -n "$DOMAIN" ]]; then
    apt-get install -y -qq certbot python3-certbot-nginx > /dev/null 2>&1
    ok "Certbot installed"
fi

# ── Step 2: Redis ─────────────────────────────────────────────────────────────
header "Step 2/8 — Configuring Redis"
systemctl enable redis-server > /dev/null 2>&1
systemctl start  redis-server
sleep 1
redis-cli ping | grep -q PONG && ok "Redis is running" || fail "Redis failed to start"

# ── Step 3: Clone / update repo ──────────────────────────────────────────────
header "Step 3/8 — Deploying application"
if [[ -d "$APP_DIR/.git" ]]; then
    info "Repository exists — pulling latest changes"
    git -C "$APP_DIR" pull --quiet
    ok "Repository updated"
else
    info "Cloning repository to $APP_DIR"
    git clone --quiet "$REPO_URL" "$APP_DIR"
    ok "Repository cloned"
fi

cd "$APP_DIR"
mkdir -p storage/uploads storage/processed
ok "Storage directories ready"

# ── Step 4: Python environment ───────────────────────────────────────────────
header "Step 4/8 — Setting up Python environment"
if [[ ! -d "$APP_DIR/venv" ]]; then
    python3 -m venv "$APP_DIR/venv"
    ok "Virtual environment created"
fi
"$APP_DIR/venv/bin/pip" install --quiet -r requirements.txt
ok "Dependencies installed"

# ── Step 5: Environment file ─────────────────────────────────────────────────
header "Step 5/8 — Writing .env"
if [[ -f "$APP_DIR/.env" ]]; then
    warn ".env already exists — skipping (delete it manually to regenerate)"
else
    cat > "$APP_DIR/.env" << ENV
APP_NAME=FileProcessorAPI
UPLOAD_DIR=${APP_DIR}/storage/uploads
PROCESSED_DIR=${APP_DIR}/storage/processed
MAX_FILE_SIZE_MB=50
FILE_EXPIRY_HOURS=${FILE_EXPIRY}
REDIS_URL=redis://localhost:6379/0
DATABASE_PATH=${APP_DIR}/files.db
ENV
    ok ".env written"
fi

# ── Step 6: systemd services ─────────────────────────────────────────────────
header "Step 6/8 — Installing systemd services"

write_service() {
    local name=$1
    local exec_cmd=$2
    cat > "/etc/systemd/system/${name}.service" << SVC
[Unit]
Description=FileProcessor ${name}
After=network.target redis.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${exec_cmd}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVC
}

write_service "file_processor_api" \
    "${APP_DIR}/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${APP_PORT} --workers 2"

write_service "file_processor_worker" \
    "${APP_DIR}/venv/bin/celery -A app.workers.celery_app worker --loglevel=info --concurrency=2"

write_service "file_processor_beat" \
    "${APP_DIR}/venv/bin/celery -A app.workers.celery_app beat --loglevel=info"

systemctl daemon-reload
systemctl enable file_processor_api file_processor_worker file_processor_beat > /dev/null 2>&1
systemctl restart file_processor_api file_processor_worker file_processor_beat
sleep 3

for svc in file_processor_api file_processor_worker file_processor_beat; do
    if systemctl is-active --quiet "$svc"; then
        ok "$svc is running"
    else
        fail "$svc failed to start — check: journalctl -u $svc -n 30"
    fi
done

# ── Step 7: Nginx ─────────────────────────────────────────────────────────────
header "Step 7/8 — Configuring Nginx"

cat > /etc/nginx/sites-available/file_processor << NGINX
server {
    listen ${NGINX_PORT};
    server_name ${SERVER_NAME};
    client_max_body_size 55M;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
NGINX

# Enable site, disable default if it conflicts
ln -sf /etc/nginx/sites-available/file_processor \
       /etc/nginx/sites-enabled/file_processor

nginx -t > /dev/null 2>&1 && ok "Nginx config valid" || fail "Nginx config invalid — check: nginx -t"
systemctl reload nginx
ok "Nginx reloaded"

# ── Step 8: HTTPS ─────────────────────────────────────────────────────────────
header "Step 8/8 — HTTPS"
if [[ "$SETUP_HTTPS" == "y" && -n "$DOMAIN" ]]; then
    info "Requesting Let's Encrypt certificate for $DOMAIN"
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
            --email "admin@${DOMAIN}" --redirect \
        && ok "HTTPS configured — certificate installed" \
        || warn "Certbot failed — check DNS is pointed to this server"
else
    warn "Skipping HTTPS — run: sudo certbot --nginx -d yourdomain.com"
fi

# ── Health check ─────────────────────────────────────────────────────────────
header "Health check"
sleep 2
HEALTH=$(curl -s "http://127.0.0.1:${APP_PORT}/api/v1/health" 2>/dev/null || echo "")
if echo "$HEALTH" | grep -q '"ok"'; then
    ok "API is healthy: $HEALTH"
else
    warn "Health check failed — check: journalctl -u file_processor_api -n 30"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Deployment complete!${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════${NC}"
echo ""
if [[ -n "$DOMAIN" && "$SETUP_HTTPS" == "y" ]]; then
    echo -e "  Dashboard:  ${BOLD}https://${DOMAIN}${NC}"
    echo -e "  API docs:   ${BOLD}https://${DOMAIN}/docs${NC}"
else
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
    echo -e "  Dashboard:  ${BOLD}http://${SERVER_IP}:${NGINX_PORT}${NC}"
    echo -e "  API docs:   ${BOLD}http://${SERVER_IP}:${NGINX_PORT}/docs${NC}"
fi
echo ""
echo -e "  Logs:"
echo -e "    API:     journalctl -u file_processor_api -f"
echo -e "    Worker:  journalctl -u file_processor_worker -f"
echo -e "    Beat:    journalctl -u file_processor_beat -f"
echo ""
