#!/bin/bash
# vps-migration/backup-to-macbook.sh
# Run on the OLD VPS before destroying it.
# Creates tarballs locally, then scp's them to MacBook over Tailscale.
#
# Usage:
#   ./backup-to-macbook.sh <macbook-tailscale-ip> <macbook-username>
#
# Example:
#   ./backup-to-macbook.sh 100.112.19.124 marvinlamart

set -euo pipefail

MACBOOK_IP="${1:-}"
MB_USER="${2:-}"
if [ -z "$MACBOOK_IP" ] || [ -z "$MB_USER" ]; then
    echo "Usage: $0 <macbook-tailscale-ip> <macbook-username>"
    echo "  Find your MacBook Tailscale IP with: tailscale status"
    exit 1
fi

DEST="${MB_USER}@${MACBOOK_IP}:~/vps-migration-backup/"
STAGING="/tmp/vps-backup-staging"
TIMESTAMP=$(date '+%Y-%m-%d_%H%M%S')

echo "=== VPS Migration Backup ==="
echo "Destination: ${MB_USER}@${MACBOOK_IP}:~/vps-migration-backup/"
echo ""

# Test connectivity
echo ">>> Testing Tailscale connectivity to MacBook..."
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${MB_USER}@${MACBOOK_IP}" "echo ok" 2>/dev/null; then
    echo "ERROR: Cannot reach MacBook at $MACBOOK_IP via Tailscale"
    echo "Make sure Tailscale is running on your MacBook and SSH is enabled"
    exit 1
fi

# Create staging + destination
rm -rf "$STAGING"
mkdir -p "$STAGING"
ssh "${MB_USER}@${MACBOOK_IP}" "mkdir -p ~/vps-migration-backup/"

# ===================================================================
# 1. MinIO data (~7 GB) — tarball
# ===================================================================
echo ""
echo ">>> [1/5] Archiving MinIO data..."
tar -czf "$STAGING/minio.tar.gz" -C /data minio/
MINIO_SIZE=$(du -h "$STAGING/minio.tar.gz" | cut -f1)
echo "  Done: minio.tar.gz ($MINIO_SIZE)"

# ===================================================================
# 2. Docker volumes (~200 MB) — tarball (stop Firecrawl briefly)
# ===================================================================
echo ""
echo ">>> [2/5] Archiving Docker volumes..."
docker compose -f /opt/firecrawl/docker-compose.yaml stop 2>/dev/null || true
tar -czf "$STAGING/docker-volumes.tar.gz" -C /var/lib/docker volumes/
docker compose -f /opt/firecrawl/docker-compose.yaml start 2>/dev/null || true
VOL_SIZE=$(du -h "$STAGING/docker-volumes.tar.gz" | cut -f1)
echo "  Done: docker-volumes.tar.gz ($VOL_SIZE)"

# ===================================================================
# 3. System configs — tarball
# ===================================================================
echo ""
echo ">>> [3/5] Archiving system configs..."
mkdir -p "$STAGING/system-config/systemd"
cp /etc/systemd/system/hermes-dashboard.service \
   /etc/systemd/system/hermes-gateway.service \
   /etc/systemd/system/minio.service \
   "$STAGING/system-config/systemd/"
cp -r /etc/systemd/system/hermes-gateway.service.d \
   "$STAGING/system-config/systemd/" 2>/dev/null || true
cp /etc/default/minio "$STAGING/system-config/"
cp /opt/firecrawl/docker-compose.yaml /opt/firecrawl/.env "$STAGING/system-config/"
# Edgee Lab
mkdir -p "$STAGING/edgee-lab"
cp -r /root/edgee-lab/* "$STAGING/edgee-lab/" 2>/dev/null || true
# Cron scripts
mkdir -p "$STAGING/hermes-scripts"
cp -r /root/.hermes/scripts/* "$STAGING/hermes-scripts/" 2>/dev/null || true

tar -czf "$STAGING/configs.tar.gz" -C "$STAGING" system-config/ edgee-lab/ hermes-scripts/
CONF_SIZE=$(du -h "$STAGING/configs.tar.gz" | cut -f1)
echo "  Done: configs.tar.gz ($CONF_SIZE)"

# ===================================================================
# 4. Hermes backup zip (already done)
# ===================================================================
echo ""
echo ">>> [4/5] Staging Hermes backup..."
cp /root/hermes-final-backup.zip "$STAGING/"
HERMES_SIZE=$(du -h "$STAGING/hermes-final-backup.zip" | cut -f1)
echo "  Done: hermes-final-backup.zip ($HERMES_SIZE)"

# ===================================================================
# 5. Transfer everything to MacBook
# ===================================================================
echo ""
echo ">>> [5/5] Transferring to MacBook..."
echo "  This will take a few minutes..."

for f in minio.tar.gz docker-volumes.tar.gz configs.tar.gz hermes-final-backup.zip; do
    echo "  Sending $f..."
    scp "$STAGING/$f" "${DEST}"
done

# Cleanup
rm -rf "$STAGING"

echo ""
echo "=== Backup complete ==="
echo ""
echo "On MacBook: ls -lh ~/vps-migration-backup/"
echo ""
echo "Files transferred:"
echo "  minio.tar.gz              $MINIO_SIZE"
echo "  docker-volumes.tar.gz     $VOL_SIZE"
echo "  configs.tar.gz            $CONF_SIZE"
echo "  hermes-final-backup.zip   $HERMES_SIZE"
