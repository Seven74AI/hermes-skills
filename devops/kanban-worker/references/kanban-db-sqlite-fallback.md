# Querying Kanban DB Directly (SQLite Fallback)

When the `hermes kanban` CLI or `kanban_*` tools are unavailable, query the board's SQLite database directly. All board state is in `/root/.hermes/kanban/boards/<board>/kanban.db`.

## Schema Overview

### tasks
Core columns: `id`, `title`, `body`, `assignee`, `status`, `priority`, `created_at`, `started_at`, `completed_at`, `workspace_kind`, `workspace_path`, `consecutive_failures`, `last_heartbeat_at`, `session_id`, `skills`

Status values: `todo`, `ready`, `running`, `blocked`, `done`, `archived`, `crashed`, `reclaimed`

### task_runs
Columns: `id`, `task_id`, `profile`, `status`, `started_at`, `ended_at`, `outcome`, `summary`, `error`, `metadata` (JSON)

Outcome values: `completed`, `blocked`, `crashed`, `timed_out`, `spawn_failed`, `reclaimed`, `interrupted`

### task_comments
Columns: `id`, `task_id`, `author`, `body`, `created_at`

### task_events
Columns: `id`, `task_id`, `event`, `payload` (JSON), `created_at`

### task_links
Columns: `id`, `parent_id`, `child_id`

## Common Queries

### Status breakdown per board
```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
c = conn.cursor()
c.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY COUNT(*) DESC")
for status, count in c.fetchall():
    print(f"  {status}: {count}")
```

### Active (non-done) tasks with details
```python
c.execute("""
    SELECT id, title, assignee, status, started_at 
    FROM tasks 
    WHERE status NOT IN ('done', 'archived')
    ORDER BY status, started_at DESC
""")
```

### Task run history for a specific task
```python
c.execute("""
    SELECT id, profile, status, outcome, summary, error, started_at, ended_at
    FROM task_runs 
    WHERE task_id = ?
    ORDER BY id DESC LIMIT 10
""", (task_id,))
```

### Reviewer comments on a task
```python
c.execute("""
    SELECT id, author, body, created_at 
    FROM task_comments 
    WHERE task_id = ? AND author = 'reviewer'
    ORDER BY id DESC LIMIT 5
""", (task_id,))
```

### Recent crashed/failed runs (last N days)
```python
import time
cutoff = int(time.time()) - N * 86400
c.execute("""
    SELECT tr.task_id, tr.status, tr.outcome, tr.summary, tr.error, t.title
    FROM task_runs tr
    JOIN tasks t ON t.id = tr.task_id
    WHERE tr.started_at >= ? 
    AND tr.outcome IN ('crashed', 'failed', 'timed_out')
    ORDER BY tr.started_at DESC
    LIMIT 20
""", (cutoff,))
```

### Reviewer suggestions extraction (for audit/aggregation)
```python
# Get all reviewer comments on tasks from last 2 weeks
cutoff = int(time.time()) - 14 * 86400
c.execute("""
    SELECT t.id, t.title, tc.author, tc.body, tc.created_at
    FROM task_comments tc
    JOIN tasks t ON t.id = tc.task_id
    WHERE tc.author = 'reviewer' AND tc.created_at >= ?
    ORDER BY tc.created_at DESC
""", (cutoff,))

# Filter for actionable suggestions
suggestion_keywords = ['suggestion', 'could', 'should', 'consider', 'nit', 
                       'optional', 'recommend', 'minor', 'cosmetic', 'non-blocking']
for row in c.fetchall():
    body = (row[3] or '').lower()
    if any(kw in body for kw in suggestion_keywords):
        print(f"  {row[0]}: {row[4][:100]}...")
```

## Pitfalls

- **SQLite3 may not be installed.** Use Python's `sqlite3` module via `execute_code` instead — always available.
- **The DB file may be locked** by the running gateway process. Reads are safe (WAL mode), but writes should only be done through the kanban tools.
- **`task_events` uses `created_at` not `timestamp`** — some older schema versions differ. Check column names with `.schema task_events` first.
- **`task_runs.metadata` is JSON text** — parse with `json.loads()`.
- **Timestamps are Unix epoch seconds** — convert with `time.strftime()`.
