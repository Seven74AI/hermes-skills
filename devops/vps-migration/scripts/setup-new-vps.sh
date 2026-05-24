#!/bin/bash
# vps-migration/setup-new-vps.sh
# Run on the NEW VPS after it's provisioned.
# Installs everything from scratch, then extracts archives from MacBook.
#
# Usage:
#   ./setup-new-vps.sh <macbook-tailscale-ip> <macbook-username> [tailscale-hostname]
#
# IMPORTANT: Before running, go to Tailscale admin console and remove
# the old "vmi3304846" node so the hostname can be reused.
#
# PRE-FLIGHT:
#   1. The script will print a Tailscale auth URL — open it in your browser
#   2. Phase 2 needs SSH to your MacBook — either:
#      a) Generate a key on the new VPS: ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519
#         Then add ~/.ssh/id_ed25519.pub to MacBook authorized_keys
#      b) Or enable password auth on MacBook temporarily
#   3. MacBook must be online with Tailscale running

set -euo pipefail

MACBOOK_IP="${1:-}"
MB_USER="${2:-}"
if [ -z "$MACBOOK_IP" ] || [ -z "$MB_USER" ]; then
    echo "Usage: $0 <macbook-tailscale-ip> <macbook-username> [tailscale-hostname]"
    exit 1
fi

SRC="${MB_USER}@${MACBOOK_IP}:~/vps-migration-backup/"
TAILSCALE_HOSTNAME="${3:-vmi3304846}"
HERMES_FORK="https://github.com/Seven74AI/hermes-agent.git"
MINIO_VERSION="RELEASE.2025-09-07T16-13-09Z"
STAGING="/tmp/vps-restore-staging"

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

log "Updating system packages..."
apt update -qq && apt upgrade -y -qq

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

# Firewall
log "Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow in on tailscale0
ufw allow ssh
ufw --force enable

# ===================================================================
# PHASE 2: Fetch archives from MacBook
# ===================================================================

log "PHASE 2: Fetching backups from MacBook"

log "Testing connectivity to MacBook at ${MACBOOK_IP}..."
if ! ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "${MB_USER}@${MACBOOK_IP}" "echo ok"; then
    err "Cannot reach MacBook at ${MACBOOK_IP} via Tailscale"
fi

rm -rf "$STAGING"
mkdir -p "$STAGING"

log "Downloading archives..."
for f in minio.tar.gz docker-volumes.tar.gz configs.tar.gz hermes-final-backup.zip; do
    log "  Fetching $f..."
    scp "${SRC}${f}" "$STAGING/"
done

# ===================================================================
# PHASE 3: Restore data
# ===================================================================

log "PHASE 3: Restoring data"

# Docker volumes
log "Restoring Docker volumes..."
tar -xzf "$STAGING/docker-volumes.tar.gz" -C /var/lib/docker/

# Firecrawl
log "Setting up Firecrawl..."
mkdir -p /opt
if [ ! -d /opt/firecrawl ]; then
    git clone https://github.com/firecrawl/firecrawl.git /opt/firecrawl
fi

# Extract configs tarball
tar -xzf "$STAGING/configs.tar.gz" -C "$STAGING/"

cp "$STAGING/system-config/docker-compose.yaml" /opt/firecrawl/
cp "$STAGING/system-config/.env" /opt/firecrawl/

log "Building and starting Firecrawl (5-10 min)..."
cd /opt/firecrawl
docker compose build --quiet 2>&1 | tail -5
docker compose up -d
log "Waiting for Firecrawl (60s)..."
sleep 60
curl -s -o /dev/null -w "%{http_code}" http://localhost:3002/health 2>/dev/null || warn "Firecrawl health check failed"

# MinIO
log "Setting up MinIO..."
if [ ! -f /usr/local/bin/minio ]; then
    wget -q "https://dl.min.io/server/minio/release/linux-amd64/archive/minio.${MINIO_VERSION}" -O /usr/local/bin/minio
    chmod +x /usr/local/bin/minio
fi

mkdir -p /data
tar -xzf "$STAGING/minio.tar.gz" -C /data/

# MinIO systemd + env
cp "$STAGING/system-config/systemd/minio.service" /etc/systemd/system/
cp "$STAGING/system-config/minio" /etc/default/minio

systemctl daemon-reload
systemctl enable minio
systemctl start minio
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/minio/health/live 2>/dev/null || warn "MinIO health check failed"

# Edgee Lab (optional)
log "Setting up Edgee Lab..."
mkdir -p /root/edgee-lab
cp -r "$STAGING/edgee-lab/"* /root/edgee-lab/ 2>/dev/null || true
cd /root/edgee-lab && docker compose build 2>/dev/null || warn "Edgee Lab build skipped (non-critical)"

# ===================================================================
# PHASE 4: Hermes
# ===================================================================

log "PHASE 4: Hermes Agent"

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

# IMPORTANT: Use absolute path — 'hermes' is NOT on system PATH after deactivate
log "Restoring Hermes from backup..."
/usr/local/lib/hermes-agent/venv/bin/hermes import "$STAGING/hermes-final-backup.zip"

# Cron scripts (guard against empty dir — set -e kills script on failed glob)
log "Restoring cron scripts..."
if ls "$STAGING/hermes-scripts/"* >/dev/null 2>&1; then
    cp -r "$STAGING/hermes-scripts/"* /root/.hermes/scripts/
fi

# Root-level configs (xurl, git, gh auth, ssh keys)
log "Restoring root-level configs..."
cp /root/.xurl /root/.xurl.bak 2>/dev/null || true
cp "$STAGING/root-config/.xurl" /root/ 2>/dev/null || true
cp "$STAGING/root-config/.gitconfig" /root/ 2>/dev/null || true
cp -r "$STAGING/root-config/gh/" /root/.config/ 2>/dev/null || true
cp -r "$STAGING/root-config/.ssh/" /root/ 2>/dev/null || true
chmod 600 /root/.ssh/id_* 2>/dev/null || true

# Systemd units
log "Installing systemd units..."
cp "$STAGING/system-config/systemd/hermes-gateway.service" /etc/systemd/system/
cp "$STAGING/system-config/systemd/hermes-dashboard.service" /etc/systemd/system/
cp -r "$STAGING/system-config/systemd/hermes-gateway.service.d/" /etc/systemd/system/ 2>/dev/null || true

systemctl daemon-reload
systemctl enable hermes-gateway
systemctl enable hermes-dashboard

# ===================================================================
# PHASE 5: Start + Verify
# ===================================================================

log "PHASE 5: Starting services"

log "Starting Hermes gateway..."
systemctl start hermes-gateway
sleep 10
systemctl is-active hermes-gateway || warn "Gateway not active — check: journalctl -u hermes-gateway -n 50"

log "Starting Hermes dashboard..."
systemctl start hermes-dashboard
sleep 5
systemctl is-active hermes-dashboard || warn "Dashboard not active"

# Cleanup
rm -rf "$STAGING"

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
echo "  [ ] Cron jobs:  hermes cron list"
echo "  [ ] Obsidian:   git clone Seven74AI/obsidian-vault ~/Documents/Obsidian\ Vault/"
echo ""
log "Done. Remove backup from MacBook when verified: rm -rf ~/vps-migration-backup/"
