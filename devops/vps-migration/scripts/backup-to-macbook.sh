#!/bin/bash
# backup-to-macbook.sh — Full VPS backup via rsync over Tailscale
#
# Usage: ./backup-to-macbook.sh <MACBOOK_TAILSCALE_IP>
# Example: ./backup-to-macbook.sh 100.98.177.99
#
# Creates a timestamped backup directory on the MacBook:
#   ~/vps-backup-YYYY-MM-DD-HHMM/
#     minio/           — /data/minio (7+ GB)
#     docker-volumes/  — /var/lib/docker/volumes/
#     systemd/         — hermes-dashboard, hermes-gateway, minio .service files
#     etc-default/     — /etc/default/minio
#     firecrawl/       — docker-compose.yaml + .env
#     edgee-lab/       — /root/edgee-lab/
#     hermes-backup/   — /root/hermes-final-backup.zip

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <MACBOOK_TAILSCALE_IP>"
    echo "Example: $0 100.98.177.99"
    exit 1
fi

MACBOOK_IP="$1"
# Use root for rsync — MacBook SSH must allow root or adjust user below
MACBOOK_USER="root"
TIMESTAMP=$(date '+%Y-%m-%d-%H%M')
BACKUP_DIR="/Users/your-username/vps-backup-${TIMESTAMP}"
# Adjust MacBook username above

echo "=== VPS Backup to MacBook ==="
echo "Target: ${MACBOOK_USER}@${MACBOOK_IP}"
echo "Backup dir: ${BACKUP_DIR}"
echo ""

# Create backup directory on MacBook
ssh "${MACBOOK_USER}@${MACBOOK_IP}" "mkdir -p '${BACKUP_DIR}'/{minio,docker-volumes,systemd,etc-default,firecrawl,edgee-lab,hermes-backup}"

# 1. MinIO data (~7 GB)
echo "--- Backing up MinIO ---"
rsync -avz --progress /data/minio/ "${MACBOOK_USER}@${MACBOOK_IP}:${BACKUP_DIR}/minio/"

# 2. Docker volumes (~200 MB)
echo "--- Backing up Docker volumes ---"
rsync -avz --progress /var/lib/docker/volumes/ "${MACBOOK_USER}@${MACBOOK_IP}:${BACKUP_DIR}/docker-volumes/"

# 3. Systemd units
echo "--- Backing up systemd units ---"
rsync -avz --progress \
    /etc/systemd/system/hermes-dashboard.service \
    /etc/systemd/system/hermes-gateway.service \
    /etc/systemd/system/minio.service \
    "${MACBOOK_USER}@${MACBOOK_IP}:${BACKUP_DIR}/systemd/"

# Gateway env override (contains GITHUB_TOKEN)
if [ -f /etc/systemd/system/hermes-gateway.service.d/env.conf ]; then
    rsync -avz --progress \
        /etc/systemd/system/hermes-gateway.service.d/env.conf \
        "${MACBOOK_USER}@${MACBOOK_IP}:${BACKUP_DIR}/systemd/hermes-gateway.env.conf"
fi

# 4. MinIO credentials
echo "--- Backing up /etc/default/minio ---"
rsync -avz --progress /etc/default/minio "${MACBOOK_USER}@${MACBOOK_IP}:${BACKUP_DIR}/etc-default/"

# 5. Firecrawl compose + env
echo "--- Backing up Firecrawl config ---"
rsync -avz --progress \
    /opt/firecrawl/docker-compose.yaml \
    /opt/firecrawl/.env \
    "${MACBOOK_USER}@${MACBOOK_IP}:${BACKUP_DIR}/firecrawl/"

# 6. Edgee Lab
echo "--- Backing up Edgee Lab ---"
rsync -avz --progress /root/edgee-lab/ "${MACBOOK_USER}@${MACBOOK_IP}:${BACKUP_DIR}/edgee-lab/"

# 7. Hermes final backup (must exist — run `hermes backup -o /root/hermes-final-backup.zip` first)
echo "--- Backing up Hermes backup zip ---"
if [ -f /root/hermes-final-backup.zip ]; then
    rsync -avz --progress /root/hermes-final-backup.zip "${MACBOOK_USER}@${MACBOOK_IP}:${BACKUP_DIR}/hermes-backup/"
else
    echo "WARNING: /root/hermes-final-backup.zip not found — run 'hermes backup -o /root/hermes-final-backup.zip' first"
fi

echo ""
echo "=== Backup complete ==="
echo "Total size on MacBook:"
ssh "${MACBOOK_USER}@${MACBOOK_IP}" "du -sh '${BACKUP_DIR}'"
echo ""
echo "Backup location: ${BACKUP_DIR}"
echo "To restore, rsync each subdirectory back to the new VPS in the correct order (see SKILL.md)."
