# Kanban DB Corruption — Diagnosis & Recovery

## Symptoms

- Gateway logs: `kanban notifier tick failed: database disk image is malformed`
- Gateway logs: `kanban dispatcher: board X database is not a valid SQLite database`
- `PRAGMA integrity_check` returns non-OK (e.g., "rowid out of order")
- Boards show fewer tasks than expected, or empty
- Workers continue running as orphans (spawned before corruption)

## Root Cause

SQLite WAL mode + unclean gateway shutdown (SIGKILL during checkpoint).
WAL accumulates pending writes in `-wal` sidecar. Checkpoint merges them into
main DB. If the process is killed mid-checkpoint, the two files desynchronise →
corruption that `integrity_check` detects.

## Prevention (applied May 2026)

In `hermes_cli/kanban_db.py`, `connect()`:

```python
# After apply_wal_with_fallback():
conn.execute("PRAGMA journal_mode=DELETE")
conn.execute("PRAGMA synchronous=FULL")
```

DELETE mode writes every transaction directly to the main DB — no WAL file,
no checkpoint. Slightly more I/O but kanban write volume is low (<10 writes/min).
`synchronous=FULL` ensures fsync after every write.

All 12 kanban DBs converted. Gateway restart required after code change.

## Integrity Watchdog

Cron job `b568a8418cf3` — runs `kanban-integrity-watchdog.py` every hour.
Script: `~/.hermes/scripts/kanban-integrity-watchdog.py`

Checks all kanban DBs (dispatcher + per-board) with `PRAGMA integrity_check`.
Silent when clean. Alerts Discord + Telegram on corruption with backup path.

## Recovery Procedure

When corruption is detected:

### 1. Locate the backup
The gateway's `_guard_existing_db_is_healthy()` auto-creates timestamped backups:
```
~/.hermes/kanban.db.corrupt.YYYYMMDD_HHMMSS.bak
~/.hermes/kanban.db.corrupted-backup
~/.hermes/kanban.db.fixed  (from prior recovery)
```

### 2. Extract readable data
Even a corrupted DB often yields readable rows via Python's sqlite3:
```python
import sqlite3
src = sqlite3.connect(corrupted_backup_path)
src.row_factory = sqlite3.Row
for table in ['tasks', 'task_runs', 'task_events', 'task_links', 'task_comments']:
    try:
        rows = [dict(r) for r in src.execute(f'SELECT * FROM {table}')]
        # Import into fresh DB
    except sqlite3.DatabaseError:
        # This table is the corruption point — data lost
```

### 3. Rebuild
- Create fresh DB with schema (from `kanban_db.py` `SCHEMA_SQL`)
- Import extracted data with `INSERT OR REPLACE`
- Run `PRAGMA integrity_check` — must return `ok`
- Convert to DELETE mode + FULL sync

### 4. Reclaim orphaned tasks
Tasks with `status='running'` and dead worker PIDs → set `status='ready'`,
clear `claim_lock`, `worker_pid`, `current_run_id`. Mark associated task_runs
as `crashed`/`reclaimed`.

### 5. Verify gateway
Restart gateway. Check `hermes kanban boards list` shows correct counts.
Watch logs for 2-3 minutes for recurring errors.

## Real case (2026-05-27)

- Gateway crashed 4× on May 25 (`ModuleNotFoundError: No module named 'yaml'`)
  during WAL checkpoint → latent corruption
- Corruption surfaced May 27 01:28 when notifier read a damaged page
- Gateway self-healed at 01:48 by rebuilding DB from scratch (ALL data lost)
- Recovery: extracted 54 tasks, 64 runs, 401 events, 34 links from `.corrupted-backup`
- `kanban_notify_subs` table was the corruption point — 63 subscriptions lost
- `hermes-ops` board DB also corrupted — tasks/runs lost, events/links/comments preserved
