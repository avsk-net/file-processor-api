#!/usr/bin/env bash
# =============================================================================
# File Processor API — One-click update script
# Usage: sudo bash update.sh
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${BLUE}→${NC} $1"; }

APP_DIR="/opt/file_processor_api"

[[ $EUID -ne 0 ]] && { echo "Run as root: sudo bash update.sh"; exit 1; }

echo -e "\n${BOLD}${BLUE}── File Processor API — Update ──${NC}\n"

info "Pulling latest code"
git -C "$APP_DIR" pull --quiet
ok "Code updated"

info "Installing any new dependencies"
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
ok "Dependencies up to date"

info "Restarting services"
systemctl restart file_processor_api file_processor_worker file_processor_beat
sleep 2

for svc in file_processor_api file_processor_worker file_processor_beat; do
    systemctl is-active --quiet "$svc" \
        && ok "$svc restarted" \
        || echo "✗ $svc failed — check: journalctl -u $svc -n 20"
done

HEALTH=$(curl -s "http://127.0.0.1:8002/api/v1/health" 2>/dev/null || echo "")
echo ""
if echo "$HEALTH" | grep -q '"ok"'; then
    echo -e "${GREEN}✓ Deployment successful — API is healthy${NC}"
else
    echo "⚠ Health check failed — check logs"
fi
echo ""
