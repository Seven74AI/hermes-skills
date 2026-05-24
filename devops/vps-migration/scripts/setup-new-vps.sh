#!/bin/bash
# vps-migration/setup-new-vps.sh
# Run on the NEW VPS after it's provisioned.
# Installs everything from scratch, then restores data from MacBook.
#
# Usage:
#   chmod +x setup-new-vps.sh
#   ./setup-new-vps.sh <macbook-tailscale-ip> [tailscale-hostname]
#
# IMPORTANT: Before running, go to Tailscale admin console and remove
# the old "vmi3304846" node so the hostname can be reused.

set -euo pipefail

MACBOOK_IP="${1:-}"
if [ -z "$MACBOOK_IP" ]; then
    echo "Usage: $0 <macbook-tailscale-ip> [tailscale-hostname]"
    exit 1
fi

SRC="${MACBOOK_IP}:~/vps-migration-backup/"
TAILSCALE_HOSTNAME="${2:-vmi3304846}"
HERMES_FORK="https://github.com/Seven74AI/hermes-agent.git"
MINIO_VERSION="RELEASE.2025-09-07T16-13-09Z"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ===================================================================
# PHASE 1: Access + Runtime
# ===================================================================

log "PHASE 1: Base system + access"

# System update
log "Updating system packages..."
apt update -qq && apt upgrade -y -qq

# Core dependencies
log "Installing core packages..."
apt install -y -qq curl wget git build-essential rsync ufw python3 python3-pip python3-venv python3-dev

# Node.js 22.x
if ! command -v node &>/dev/null; then
    log "Installing Node.js 22..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt install -y -qq nodejs
fi

# Docker
if ! command -v docker &>/dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
fi

# Tailscale
if ! command -v tailscale &>/dev/null; then
    log "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | bash
fi

log "Starting Tailscale with hostname: ${TAILSCALE_HOSTNAME}"
tailscale up --hostname="${TAILSCALE_HOSTNAME}" --accept-routes --ssh

log "Waiting for Tailscale to connect (30s)..."
sleep 30
tailscale status | head -5

# Firewall: allow only Tailscale + SSH
log "Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow in on tailscale0
ufw allow ssh
ufw --force enable

# ===================================================================
# PHASE 2: Storage + Services
# ===================================================================

log "PHASE 2: Storage + Docker services"

# Test MacBook connectivity
log "Testing connectivity to MacBook at ${MACBOOK_IP}..."
if ! ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$MACBOOK_IP" "echo ok"; then
    err "Cannot reach MacBook at ${MACBOOK_IP} via Tailscale"
fi

# Docker volumes
log "Restoring Docker volumes..."
rsync -avz --progress "${SRC}docker-volumes/" /var/lib/docker/volumes/

# Firecrawl
log "Setting up Firecrawl..."
mkdir -p /opt
if [ ! -d /opt/firecrawl ]; then
    git clone https://github.com/firecrawl/firecrawl.git /opt/firecrawl
fi
rsync -avz "${SRC}firecrawl-config/docker-compose.yaml" /opt/firecrawl/
rsync -avz "${SRC}firecrawl-config/.env" /opt/firecrawl/

log "Building and starting Firecrawl (this takes a while)..."
cd /opt/firecrawl
docker compose build --quiet 2>&1 | tail -5
docker compose up -d
log "Waiting for Firecrawl to be healthy (60s)..."
sleep 60
curl -s -o /dev/null -w "%{http_code}" http://localhost:3002/health 2>/dev/null || warn "Firecrawl health check failed — check: docker compose logs"

# MinIO
log "Setting up MinIO..."
if [ ! -f /usr/local/bin/minio ]; then
    wget -q "https://dl.min.io/server/minio/release/linux-amd64/archive/minio.${MINIO_VERSION}" -O /usr/local/bin/minio
    chmod +x /usr/local/bin/minio
fi

mkdir -p /data/minio
rsync -avz --progress "${SRC}minio/" /data/minio/

# MinIO systemd
rsync -avz "${SRC}system-config/systemd/minio.service" /etc/systemd/system/
scp "${SRC}system-config/minio" /etc/default/minio

systemctl daemon-reload
systemctl enable minio
systemctl start minio
log "Waiting for MinIO..."
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/minio/health/live 2>/dev/null || warn "MinIO health check failed"

# Edgee Lab
log "Setting up Edgee Lab..."
mkdir -p /root/edgee-lab
rsync -avz --progress "${SRC}edgee-lab/" /root/edgee-lab/
cd /root/edgee-lab && docker compose build 2>/dev/null || warn "Edgee Lab build skipped (Dockerfile error — non-critical)"

# ===================================================================
# PHASE 3: Hermes
# ===================================================================

log "PHASE 3: Hermes Agent"

# Clone and install
if [ ! -d /usr/local/lib/hermes-agent ]; then
    log "Cloning Hermes agent..."
    git clone "$HERMES_FORK" /usr/local/lib/hermes-agent
    cd /usr/local/lib/hermes-agent
    git remote add upstream https://github.com/NousResearch/hermes-agent.git 2>/dev/null || true
fi

cd /usr/local/lib/hermes-agent
python3 -m venv venv
source venv/bin/activate
pip install -e . -q 2>&1 | tail -3
deactivate

# Restore Hermes data from backup
log "Restoring Hermes data from backup..."
rsync -avz "${SRC}hermes-backup/hermes-final-backup.zip" /root/
hermes import /root/hermes-final-backup.zip

# Restore cron scripts
log "Restoring cron scripts..."
rsync -avz --progress "${SRC}hermes-scripts/" /root/.hermes/scripts/

# Install systemd units
log "Installing systemd units..."
rsync -avz "${SRC}system-config/systemd/hermes-gateway.service" /etc/systemd/system/
rsync -avz "${SRC}system-config/systemd/hermes-dashboard.service" /etc/systemd/system/
rsync -avz "${SRC}system-config/systemd/hermes-gateway.service.d/" /etc/systemd/system/hermes-gateway.service.d/ 2>/dev/null || true

systemctl daemon-reload
systemctl enable hermes-gateway
systemctl enable hermes-dashboard

# ===================================================================
# PHASE 4: Start + Verify
# ===================================================================

log "PHASE 4: Starting services"

log "Starting Hermes gateway..."
systemctl start hermes-gateway
sleep 10
systemctl is-active hermes-gateway || warn "Gateway not active — check: journalctl -u hermes-gateway -n 50"

log "Starting Hermes dashboard..."
systemctl start hermes-dashboard
sleep 5
systemctl is-active hermes-dashboard || warn "Dashboard not active"

log ""
log "=============================================="
log "VERIFICATION CHECKLIST"
log "=============================================="
echo ""
echo "  [ ] Firecrawl:  curl http://localhost:3002/health"
echo "  [ ] MinIO:      curl http://localhost:9000/minio/health/live"
echo "  [ ] MinIO (TS): curl http://${TAILSCALE_HOSTNAME}.tail5c02a1.ts.net:9000/minio/health/live"
echo "  [ ] Gateway:    systemctl status hermes-gateway"
echo "  [ ] Dashboard:  curl http://localhost:9119/"
echo "  [ ] Cron jobs:  hermes cron list (verify all 26+ jobs exist)"
echo "  [ ] Test msg:   send a test message from the gateway"
echo "  [ ] Obsidian:   git clone Seven74AI/obsidian-vault to ~/Documents/"
echo ""
log "Done. Remove backup from MacBook when verified: rm -rf ~/vps-migration-backup/"
