# Kanban DB Schema — `tasks` Table

Column reference for SQLite queries against `~/.hermes/kanban/boards/<board>/kanban.db`.
Use `PRAGMA table_info(tasks)` to verify if the schema has been updated since this reference.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Task ID, e.g. `t_abc12345` |
| `title` | TEXT | Task title |
| `body` | TEXT | Task description/markdown body |
| `assignee` | TEXT | Profile name (coder, reviewer, planner, researcher, hermes-devops) |
| `status` | TEXT | `ready`, `in_progress`, `blocked`, `done`, `scheduled`, `archived` |
| `priority` | INTEGER | Priority (lower = higher) |
| `created_by` | TEXT | Who created the task |
| `created_at` | INTEGER | Unix timestamp of creation |
| `started_at` | INTEGER | Unix timestamp when worker picked it up |
| `completed_at` | INTEGER | Unix timestamp when marked done |
| `workspace_kind` | TEXT | Workspace type (e.g. `git`) |
| `workspace_path` | TEXT | Path to the workspace directory |
| `claim_lock` | TEXT | Lock token for worker claim |
| `claim_expires` | INTEGER | Unix timestamp when claim expires |
| `tenant` | TEXT | Project tenant (shop, the-swarm, music-library, etc.) |
| `result` | TEXT | Completion summary |
| `idempotency_key` | TEXT | Dedup key for idempotent creates |
| `consecutive_failures` | INTEGER | Count of consecutive failures |
| `worker_pid` | INTEGER | PID of the worker process |
| `last_failure_error` | TEXT | Last error message from a failed run |
| `max_runtime_seconds` | INTEGER | Safety-net timeout (NULL = no limit!) |
| `last_heartbeat_at` | INTEGER | Unix timestamp of last worker heartbeat |
| `current_run_id` | INTEGER | Current run identifier |
| `workflow_template_id` | TEXT | Workflow template reference |
| `current_step_key` | TEXT | Current workflow step |
| `skills` | TEXT | JSON array of skill names, e.g. `["shop","kanban-project-workflow"]` |
| `max_retries` | INTEGER | Max retry count |
| `branch_name` | TEXT | Git branch name used by the worker |
| `model_override` | TEXT | Model override for this task |
| `session_id` | TEXT | Hermes session ID for token tracking |

## Common query patterns

### Board overview (all boards)
```python
import sqlite3, glob, os

for db_path in sorted(glob.glob('/root/.hermes/kanban/boards/*/kanban.db')):
    board = os.path.basename(os.path.dirname(db_path))
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    total = db.execute("SELECT count(*) FROM tasks").fetchone()[0]
    if total == 0:
        db.close()
        continue
    counts = db.execute("""
        SELECT status, count(*) as n FROM tasks GROUP BY status
    """).fetchall()
    # ... process counts, running tasks, blocked tasks
    db.close()
```

### Running tasks with heartbeat age
```sql
SELECT id, title, assignee, last_heartbeat_at, started_at, worker_pid
FROM tasks WHERE status = 'in_progress'
ORDER BY started_at DESC
```

### Blocked tasks with reasons
```sql
SELECT t.id, t.title, t.assignee
FROM tasks t
WHERE t.status = 'blocked'
ORDER BY t.started_at DESC
```

### Scheduled tasks (invisible to dispatcher + pre-spawn watchdog)
```sql
SELECT id, title, assignee
FROM tasks WHERE status = 'scheduled'
ORDER BY created_at DESC
```

### Tasks with NULL max_runtime_seconds (no timeout — can run indefinitely)
```sql
SELECT id, title, status
FROM tasks WHERE max_runtime_seconds IS NULL AND status = 'ready'
```

## Timestamps

All timestamps are Unix epoch integers (seconds). Convert with `datetime.utcfromtimestamp(ts)`.
There is NO `updated_at` column — use `started_at`, `completed_at`, or `last_heartbeat_at` depending on context.

## Related tables

- `task_comments` — comments on tasks (columns: id, task_id, body, type, author, created_at, reason, metadata)
- `sessions` — session tracking (columns: id, task_id, session_id, model, started_at, ended_at, tokens_in, tokens_out, status)
