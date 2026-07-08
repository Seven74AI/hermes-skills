# Kanban DB Recovery (SQLite WAL Corruption)

The kanban SQLite DB can develop index corruption, typically manifesting as:
```
kanban: could not initialize database: Refusing to open corrupt kanban DB at <path>: integrity_check returned 'wrong # of entries in index idx_notify_task'
```

The kanban CLI refuses to open corrupted DBs and auto-preserves a `.bak` copy.

## Recovery Pattern

```bash
cd ~/.hermes/kanban/boards/<board>/

# 1. Identify the corrupt index/table from the error message
#    e.g., "wrong # of entries in index idx_notify_task"

# 2. Drop the corrupt index and its table
sqlite3 kanban.db "DROP INDEX IF EXISTS idx_notify_task; \
                   DROP TABLE IF EXISTS kanban_notify_subs; \
                   PRAGMA integrity_check;"
# Must return "ok"

# 3. Recreate the table + index from another board's schema
sqlite3 ~/.hermes/kanban/boards/shop/kanban.db ".schema kanban_notify_subs" | \
  sqlite3 kanban.db
```

The backup at `kanban.db.corrupt.<timestamp>.bak` is preserved for forensic inspection.

## Common Corrupt Targets

- **`idx_notify_task`** — index on `kanban_notify_subs(task_id)`. Safe to drop because subscriptions are disposable (just re-subscribe).
- If `idx_task_events_task_id` or core tables are corrupt, attempt `.dump` recovery first or restore from a healthy snapshot.

## Pitfall: Lost Subscriptions

After dropping `kanban_notify_subs`, re-subscribe any Telegram notifications that were active on the board. Subscriptions are NOT recoverable from the backup — the backup has the same corruption.
