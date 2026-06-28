#!/bin/bash
# Sanitized Hermes backup — strips .env and auth.json before pushing
# Replaces the LLM-driven backup cron. Run by cronjob every 2h.
# Deployed: June 13, 2026 — replaces LLM cron job 8d322a4ec332
set -euo pipefail

TIMESTAMP=$(date '+%Y%m%d-%H%M%S')
BACKUP_NAME="hermes-critical-${TIMESTAMP}.tar.gz"
BACKUP_DIR="/root/.hermes/backups"
TMP_DIR=$(mktemp -d)
KEEP=2  # Keep last N backups

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "[$(date -Iseconds)] Starting sanitized backup..." >&2

# 1. Create quick backup (hermes backup ALWAYS produces .zip, regardless of -o filename)
#    Use -o with directory only, then glob for the result
hermes backup -q -o "$TMP_DIR" 2>&1
RAW_ZIP=$(ls -t "$TMP_DIR"/hermes-backup-*.zip 2>/dev/null | head -1)
if [ -z "$RAW_ZIP" ] || [ ! -f "$RAW_ZIP" ]; then
    echo "[$(date -Iseconds)] FATAL: hermes backup produced no output file in $TMP_DIR" >&2
    exit 1
hermes backup -q -o "$TMP_DIR" 2>&1
RAW_ZIP=$(ls -t "$TMP_DIR"/hermes-backup-*.zip 2>/dev/null | head -1)
if [ -z "$RAW_ZIP" ] || [ ! -f "$RAW_ZIP" ]; then
    echo "[$(date -Iseconds)] FATAL: backup produced no output file" >&2
    exit 1
fi
echo "[$(date -Iseconds)] Backup created: $(basename "$RAW_ZIP") ($(du -h "$RAW_ZIP" | cut -f1))" >&2

# 2. Strip .env and auth.json from the archive
cd "$TMP_DIR"
mkdir stripped
unzip -q "$RAW_ZIP" -d stripped/

if [ -f stripped/.env ]; then
    rm -f stripped/.env
    echo "[$(date -Iseconds)] Stripped .env from backup" >&2
fi
if [ -f stripped/auth.json ]; then
    rm -f stripped/auth.json
    echo "[$(date -Iseconds)] Stripped auth.json from backup" >&2
fi

# 3. Repack
cd stripped
tar czf "../${BACKUP_NAME}" .
cd ..
rm -rf stripped

echo "[$(date -Iseconds)] Repacked (${BACKUP_NAME}), size: $(du -h ${BACKUP_NAME} | cut -f1)" >&2

# 4. Copy to backup repo
cp "$BACKUP_NAME" "$BACKUP_DIR/"
cd "$BACKUP_DIR"

# 5. Git operations (if token is available)
if [ -f /root/.hermes/.env ]; then
    TOKEN=$(grep '^GITHUB_TOKEN=' /root/.hermes/.env | head -1 | cut -d= -f2-)
    if [ -n "$TOKEN" ]; then
        export GIT_TERMINAL_PROMPT=0
        git remote set-url origin "https://git:${TOKEN}@github.com/Seven74AI/hermes-backup.git" 2>/dev/null || true
        git pull origin main 2>&1 || echo "Pull failed (may be first push)" >&2
        git add "$BACKUP_NAME"
        git commit -m "sanitized backup ${TIMESTAMP} — rotate (keep ${KEEP})" 2>&1 || echo "Nothing to commit (already up to date?)" >&2
        
        # 6. Rotation: keep last K backups
        BACKUP_FILES=$(ls -1t hermes-critical-*.tar.gz 2>/dev/null || true)
        COUNT=$(echo "$BACKUP_FILES" | grep -c . || echo 0)
        if [ "$COUNT" -gt "$KEEP" ]; then
            OLD=$(echo "$BACKUP_FILES" | tail -n +$((KEEP+1)))
            for f in $OLD; do
                git rm "$f" 2>/dev/null || rm -f "$f"
                echo "[$(date -Iseconds)] Pruned old backup: $f" >&2
            done
            git commit -m "prune: keep last ${KEEP} backups" 2>&1 || true
        fi
        
        # 7. Push
        git push origin main 2>&1
        echo "[$(date -Iseconds)] Pushed to GitHub" >&2
    else
        echo "[$(date -Iseconds)] WARNING: GITHUB_TOKEN not found, skipping push" >&2
    fi
else
    echo "[$(date -Iseconds)] WARNING: .env not found, skipping push" >&2
fi

# 8. Prune state-snapshots
if [ -f /root/.hermes/scripts/prune-snapshots.py ]; then
    python3 /root/.hermes/scripts/prune-snapshots.py 2>&1 || true
fi

echo "[$(date -Iseconds)] Backup complete ✓" >&2
echo "Sanitized backup created: ${BACKUP_NAME} (no .env/auth.json)"
