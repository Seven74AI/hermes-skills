# /tmp Backup Residue Patterns

Backup operations leave residue in two forms — only one was originally caught.

## Files (caught by 2p, pre-patch)
- `hermes-backup-*.zip`, `hermes-backup-*.tar.gz`
- `hermes-critical-*.zip`, `hermes-critical-*.tar.gz`
- `hermes-final-*.zip`, `hermes-final-*.tar.gz`
- `hermes-test-backup.zip` (1058M, 2026-05-29 — not `hermes-*` prefix)

## Unpacked Directories (NOT caught pre-patch)
The backup cron sometimes unpacks archives into directories before uploading, leaving the directory behind:
- `hermes-backup-20260529-072807/` (496M)
- `hermes-critical-20260529-094443/` (506M)

These match the `hermes-backup*`/`hermes-critical*` prefix but are **directories**, not files.
They don't match the project-clone heuristic in 2eb (no `.git`, `package.json`, or `node_modules`).
They're not caught by 2e (files only, and <24h old).
Post-patch, 2p Phase 2 catches them.

## Orphaned SQLite DBs
- `tmpz3xyvcic.db` (1.6G) — likely from a failed data operation; <24h so 2e missed it
- `tmpg_ul35eg.db` (1.4G) — caught by 2e (>24h)
No automated step catches these when fresh. If they're clearly temp (tmp* prefix in /tmp), delete manually.
