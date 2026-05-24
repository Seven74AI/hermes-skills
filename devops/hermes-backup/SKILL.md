---
name: hermes-backup
description: Set up and maintain Hermes Agent backups — cron jobs, Git LFS quotas, rotation strategy, and size troubleshooting.
---

Backup strategy for a Hermes Agent installation. Covers both quick backups (config + state + auth, every 2h) and full backups (sessions included, daily).

## Trigger

Use when setting up, troubleshooting, or modifying Hermes backup cron jobs, or when backup size explodes or Git LFS quotas are at risk.

## Backup types

| Type | Command | Contents | Typical size | Frequency |
|------|---------|----------|-------------|-----------|
| Quick | `hermes backup -q` | config, state.db, .env, auth, cron | ~130 MB | 2h |
| Full | `hermes backup` | Quick + sessions + state-snapshots | 130-500 MB (can explode) | Daily |

## Git LFS is the real limit

The backup repo uses Git LFS for .zip files (`.gitattributes` with LFS filter). GitHub's limits:

- **1 GB free LFS storage** — the hard cap
- **1 GB free LFS bandwidth/month** — downloads

GitHub's repo size limit (5 GB) does NOT apply to LFS objects — only the bare repo counts. LFS objects are tracked separately.

**A single 500 MB backup consumes half the free LFS quota.** Daily PR-based backups with no rotation will exhaust the quota in 2-3 days.

## Recommended pattern: rotation + commit direct to main

Do NOT use PR-per-backup. Each PR keeps the file in git history forever, and LFS never deletes old objects unless explicitly purged. Instead:

1. Commit the dated backup file directly to main
2. After the commit, delete all but the N most recent backup files (rotation)
3. Push

This keeps LFS storage stable at N × backup_size.

```bash
# Rotation: keep 3 most recent
BACKUP_FILE="hermes-backup-$(date '+%Y-%m-%d').zip"
hermes backup -o /tmp/$BACKUP_FILE
cp /tmp/$BACKUP_FILE /tmp/hermes-backup-repo/
cd /tmp/hermes-backup-repo
git pull
git add $BACKUP_FILE
git commit -m "Full backup $(date '+%Y-%m-%d')"
# Delete all but 3 most recent
ls -t hermes-backup-*.zip | tail -n +4 | xargs -r git rm
git commit -m "Rotation" && git push
```

## Backup size explosion

`hermes backup` includes state-snapshots. If snapshots accumulate (not cleaned regularly), backup size can grow from ~130 MB to 1+ GB. Monitor with:

```bash
du -sh ~/.hermes/state-snapshots/
ls ~/.hermes/state-snapshots/ | wc -l
```

The disk watchdog + cleanup agent should keep snapshots trimmed.

## Cron job settings

| Setting | Value | Reason |
|---------|-------|--------|
| `timeout` (foreground) | 600s | Full backup can take >300s when large |
| `enabled_toolsets` | `["terminal"]` | Backup is a pure shell operation |
| `deliver` | `local` | Errors stay in the job log, no spam |

See `references/backup-failure-may2026.md` for a real-world debugging trace (May 2026 state-snapshot explosion).

## Debugging cron errors

When a backup cron shows `last_status: error`:

1. `cronjob(action='list')` — identify the failed job
2. `session_search(query="backup PR", limit=5)` — find related sessions (cron sessions are named `cron_<job_id>_<timestamp>`)
3. Scroll into the cron session: `session_search(session_id="...", around_message_id=<id>, window=10)`
4. Look for: timeouts (300s foreground cap), disk-full errors, approval-needed blocks on `rm`, or 0-message sessions (agent crash/infra failure)

## Pitfalls

- **PR-per-backup + LFS = quota doom**: Every PR keeps the file in history. LFS objects are never garbage-collected automatically. Use rotation + direct-to-main commits.
- **Foreground timeout**: `hermes backup` in foreground defaults to 300s. Large backups (>500 MB) will timeout. Use `background=true` with `notify_on_complete=true` or set `timeout=600`.
- **`rm` in /tmp needs approval**: The terminal tool may block `rm` commands in `/tmp` as "delete in root path". Cleanup should happen inside the backup repo directory.
- **State-snapshots bloat**: If `hermes backup` produces abnormally large files, check `~/.hermes/state-snapshots/` first.
- **Repo missing after cleanup**: `/tmp/hermes-backup-repo/` may be cleaned by the disk cleanup agent. Re-clone if needed: `git clone https://github.com/Seven74AI/hermes-backup.git /tmp/hermes-backup-repo`
