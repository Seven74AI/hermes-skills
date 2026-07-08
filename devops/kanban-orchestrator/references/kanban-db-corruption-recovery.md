# Kanban DB Corruption — Diagnosis & Recovery

## Symptoms

- Gateway logs: `kanban dispatcher: tick failed on board <name>` with `sqlite3.OperationalError: disk I/O error` in `release_stale_claims`
- Gateway logs: `kanban dispatcher stuck: ready queue non-empty for N consecutive ticks but 0 workers spawned`
- Gateway logs: `kanban notifier tick failed: cannot rollback - no transaction is active` (cascading from the dispatcher crash)
- `PRAGMA integrity_check` returns non-OK
- **Board-specific**: only affects one board, others dispatch normally

## Root Cause (candidates — definitive cause unknown)

The most common trigger is **concurrent WAL writes + read** under heavy load.
Observed pattern: a bulk operation (e.g. `hermes kanban archive` archiving 7+
tasks in sequence) writes to the WAL, the WAL auto-checkpoint runs, and a
concurrent reader (dispatcher tick) hits an inconsistent page state. The error
persists across fresh connections (it's in the DB file, not connection state)
and can self-heal after hours when the WAL is replayed.

SQLite `synchronous=NORMAL` (what kanban DBs use) is **safe from corruption**
per SQLite docs — the WAL→DELETE migration documented below was aspirational
and never applied. The user decided to keep WAL mode.

## Disk I/O error pattern (specific to dispatcher)

```
sqlite3.OperationalError: disk I/O error
  at kanban_db.py release_stale_claims → conn.execute(SELECT ... WHERE status='running')
```

With `_is_corrupt_board_db_error` in `gateway/run.py` (updated Jul 2026),
this now **disables the board** (same as "file is not a database") instead
of crash-looping every 60s. The board re-enables automatically when the DB
fingerprint changes (file modification triggers re-check).

## Prevention

- **Gateway restart** is the fastest recovery — new process, fresh connections.
- **Per-board max_spawn** via `board.json` (`"max_spawn": 1`) for resource-heavy
  boards (knowledge-base, kb-agent). Global default is 5.
- **Integrity re-check** runs every hour (not just once at startup) via
  `_guard_existing_db_is_healthy` in `kanban_db.py`. Catches drift before
  it cascades into dispatch outages.
