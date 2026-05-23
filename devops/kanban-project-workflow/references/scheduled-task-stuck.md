# Pitfall: Scheduled Tasks Stuck After Parent Completes

## Symptom

A task shows `scheduled` status indefinitely — hours or days after its parent completed. The dispatcher ignores `scheduled` tasks (only picks up `ready`). The pre-spawn watchdog only scans `ready` tasks, so NULL `skills` or NULL `max_runtime_seconds` on `scheduled` tasks go undetected.

## Root Cause

The parent→child promotion chain can silently fail. When a child is created while its parent is blocked, the child gets status `scheduled` ("Promote to ready — parent blocked for review"). When the parent later completes, the auto-promotion `scheduled → ready` should fire — but doesn't always.

## Detection

```bash
# Find stuck scheduled tasks across all boards
python3 -c "
import sqlite3, glob
for db in glob.glob('/root/.hermes/kanban/boards/*/kanban.db'):
    conn = sqlite3.connect(db)
    rows = conn.execute(\"SELECT id, title, skills, max_runtime_seconds FROM tasks WHERE status='scheduled'\").fetchall()
    for r in rows:
        print(f'{db}: {r[0]} | skills={\"NULL\" if r[2] is None else \"set\"} | mrt={r[3]}')
    conn.close()
"
```

## Fix

Three-step manual fix:

```python
import sqlite3

db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')

# 1. Set status to ready, add skills + max_runtime_seconds
db.execute("""
    UPDATE tasks 
    SET status = 'ready', 
        skills = '<role-appropriate-skills>', 
        max_runtime_seconds = 3600 
    WHERE id = '<task_id>'
""")
db.commit()
db.close()
```

```bash
# 2. Verify dry-run
hermes kanban --board <board> dispatch --dry-run

# 3. Dispatch for real
hermes kanban --board <board> dispatch
```

## Real Case

hermes-skills board, 2026-05-22: `t_edff11e9` stuck `scheduled` for 3 days. Parent `t_14b8bc08` completed 2026-05-19 21:10. Child had `skills=NULL` and `max_runtime_seconds=NULL`. Pre-spawn watchdog didn't catch it because it only scans `ready` tasks.

## Why Pre-Spawn Watchdog Misses It

The pre-spawn watchdog (`pre-spawn-watchdog.py`) scans `WHERE status='ready'`. `scheduled` tasks are invisible to it. If you want to extend coverage, add a separate query for `status='scheduled'` — but note that legitimately scheduled tasks (parent still running) would also be flagged. The better fix is to ensure the promotion chain never silently fails.
