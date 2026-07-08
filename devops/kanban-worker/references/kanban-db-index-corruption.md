# Kanban DB — Index Corruption Recovery

## Symptom

```
kanban: could not initialize database: Refusing to open corrupt kanban DB at
/path/to/kanban.db: integrity_check returned 'wrong # of entries in index idx_notify_task'.
Original preserved; backup at kanban.db.corrupt.<timestamp>.bak.
```

The DB refuses to open. A backup is created automatically.

## Root cause

SQLite WAL checkpointing under concurrent load (kanban archive + dispatch)
can corrupt individual indexes. The data itself is usually intact — only the
index is broken.

## Recovery (3-step)

### Step 1: Identify the corrupt index

The integrity_check message names the index directly (`idx_notify_task`).

### Step 2: Drop the corrupt index and its table

```bash
cp kanban.db.corrupt.<timestamp>.bak kanban.db
sqlite3 kanban.db "DROP INDEX IF EXISTS idx_notify_task; DROP TABLE IF EXISTS kanban_notify_subs; PRAGMA integrity_check;"
# Should return: ok
```

If integrity_check still fails, drop additional corrupt indexes/tables until it passes.
The data tables (`tasks`, `task_comments`, `task_runs`, `task_events`, `task_links`)
are the critical ones — the notification subscriptions table is non-critical.

### Step 3: Recreate the table from a known-good schema

Copy the schema from another board's DB:

```bash
sqlite3 /root/.hermes/kanban/boards/<healthy-board>/kanban.db \
  ".schema kanban_notify_subs" | sqlite3 /root/.hermes/kanban/boards/<corrupt-board>/kanban.db
```

Then re-subscribe any lost notifications:

```bash
hermes kanban --board <board> notify-subscribe <task_id> --platform telegram --chat-id "..."
```

### Verification

```bash
sqlite3 /root/.hermes/kanban/boards/<board>/kanban.db "PRAGMA integrity_check;"
# Must return: ok

hermes kanban --board <board> show <any_task_id>
# Must work without errors
```

## Real case (2026-07-07, music-library board)

- Triggered by `hermes kanban notify-subscribe` during concurrent coder worker dispatch
- `idx_notify_task` had wrong entry count
- Both auto-backups were also corrupted (same error)
- Dropping the index + table → integrity_check passed
- Schema recreated from shop board
- Lost 1 notification subscription (re-subscribed manually)

## Prevention

The fix is the same as general SQLite WAL corruption prevention:
- Run `PRAGMA integrity_check` periodically (every 100 ticks or hourly)
- Consider safe-mode auto-restart if corruption is detected mid-session
