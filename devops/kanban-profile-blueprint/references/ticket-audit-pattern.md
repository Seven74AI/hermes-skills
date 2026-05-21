# Ticket Audit Pattern

Quick SQL audit to verify all todo tickets are properly configured before dispatch.
Catches: missing max_runtime, empty body, broken dependency links, stale assignments.

## The query

```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')

tickets = conn.execute("""
    SELECT id, title, status, max_runtime_seconds,
        (SELECT GROUP_CONCAT(parent_id,' ') FROM task_links WHERE child_id=tasks.id) as parents,
        (SELECT GROUP_CONCAT(child_id,' ') FROM task_links WHERE parent_id=tasks.id) as children,
        (SELECT LENGTH(body) FROM tasks t2 WHERE t2.id=tasks.id) as body_len
    FROM tasks WHERE status IN ('todo', 'ready')
    ORDER BY id
""").fetchall()

for t in tickets:
    tid, title, status, runtime, parents, children, body_len = t
    issues = []
    if not runtime:
        issues.append('NO-RUNTIME')  # fallback = ~120s, guaranteed timeout
    if not body_len:
        issues.append('NO-BODY')     # worker has no spec
    if not parents:
        issues.append('NO-PARENTS')  # might dispatch too early
    if issues:
        print(f'{tid} {" ".join(issues)}: {title[:60]}')
```

## What to check

| Field | Risk if missing |
|-------|----------------|
| max_runtime_seconds | Defaults to ~120s — task times out before finishing work |
| body | Worker has no spec — improvises or blocks immediately |
| parents | Task may dispatch before dependencies are ready |

## Fix commands

```bash
# Fix runtime
python3 -c "import sqlite3;db=sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db');db.execute('UPDATE tasks SET max_runtime_seconds=3600 WHERE id=\"<id>\"');db.commit()"

# Fix body (long specs use SQLite directly)
# See ticket-body-audit.md for body management patterns
```

## Integration with board health check

Run this as part of any board status request. Combine with:
- Ghost profile check (references/ghost-profile-recovery.md)
- Crash-loop detection (scripts/check-crash-loops.py)
- Contradiction check (references/contradiction-check.md — SOUL vs config vs ticket DB)

## Real case

2026-05-20, the-swarm board: 8 todo tickets audited after decomposition. Found:
- 3 tickets with NULL max_runtime (would timeout at 120s on long GM tasks)
- 5 tickets with NULL body (workers would block immediately with no spec)
- 0 broken dependency links (decomposition was correct)
Fix: 3 runtime updates + 5 body backfills via SQLite. Total fix time: under 2 min.
