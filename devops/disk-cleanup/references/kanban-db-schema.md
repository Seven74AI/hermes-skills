# Kanban DB Schema — tasks table

Key columns relevant to workspace cleanup and task lifecycle management.

## Schema

```sql
CREATE TABLE tasks (
    id                    TEXT PRIMARY KEY,
    title                 TEXT,
    body                  TEXT,
    assignee              TEXT,
    status                TEXT,       -- ready, todo, in_progress, blocked, done, archived
    priority              TEXT,
    created_by            TEXT,
    created_at            TEXT,       -- datetime string
    started_at            TEXT,       -- datetime string
    completed_at          TEXT,       -- Unix timestamp (INTEGER stored as TEXT!)
    workspace_kind        TEXT,
    workspace_path        TEXT,
    claim_lock            TEXT,
    claim_expires         TEXT,
    tenant                TEXT,
    result                TEXT,
    idempotency_key       TEXT,
    consecutive_failures  INTEGER,
    worker_pid            INTEGER,
    last_failure_error    TEXT,
    max_runtime_seconds   INTEGER,
    last_heartbeat_at     TEXT,
    current_run_id        INTEGER,
    workflow_template_id  TEXT,
    current_step_key      TEXT,
    skills                TEXT,
    max_retries           INTEGER
);
```

## Pitfalls

### `completed_at` is a Unix timestamp, not a datetime string

Query pattern that WORKS:
```python
import time
cutoff = int(time.time()) - 300  # 5 minutes ago
conn.execute(
    "SELECT id FROM tasks WHERE status IN ('done', 'archived') "
    "AND CAST(completed_at AS INTEGER) > 0 "
    "AND CAST(completed_at AS INTEGER) < ?",
    (cutoff,)
)
```

Query pattern that FAILS:
```sql
-- THIS DOES NOT WORK — completed_at is an integer, not a datetime string
SELECT id FROM tasks WHERE status IN ('done', 'archived')
AND updated_at < datetime('now', '-1 hour')
--                    ^^^^^^^^^^ column does not exist
--      ^^^^^^^^^^ column does not exist
```

### `transition archive` silently fails from `blocked` state

`hermes kanban --board <board> transition <id> archive` returns success but the task stays `blocked`. Use direct SQL:
```sql
UPDATE tasks SET status = 'archived', completed_at = <unix_ts> WHERE id = '<tid>';
```

### `reclaim` is single-task only

`hermes kanban reclaim` accepts exactly one task ID. Loop for multiple.

### `--board` goes BEFORE the subcommand

`hermes kanban --board <slug> list` ✓
`hermes kanban list --board <slug>` ✗
