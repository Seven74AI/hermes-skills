# Ticket Body Audit

How to find and fix tickets created without a body (worker has no spec, will block).

## Why

`hermes kanban create` via CLI without `--body` flag leaves `body=NULL` in DB.
When the dispatcher spawns a worker, the worker reads an empty body and blocks
immediately with "no task specification" — wasting a slot and retry budget.

## Detection

```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
bad = conn.execute(
    "SELECT id, title FROM tasks WHERE body IS NULL AND status IN ('todo','ready')"
).fetchall()
for tid, title in bad:
    print(f'{tid}: {title}')
conn.close()
```

## Fix: backfill body via SQLite

```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')

body = """## Feature Name

### Spec
...

### Files
- New: ...
- Modify: ...

### Testing (TDD)
- RUN: terminal("pnpm test:all", background=true, notify_on_complete=true)
- Wait: process(action="wait", timeout=3600)
- Vitest: ...
- Playwright: ...
"""

conn.execute('UPDATE tasks SET body=? WHERE id=?', (body, '<tid>'))
conn.commit()
conn.close()
```

## Prevention

Always include `--body` when creating tickets via CLI, or use explicit body
in the `kanban_create` tool call. When decomposing bundled tickets, split the
original body content across the new atomic tickets.

## Checklist for body content

Every ticket body should include:
- **Spec**: what to implement, constraints, edge cases
- **Files**: `src/...` paths (new and modified)
- **Testing (TDD)**: what tests to write, with the background+wait command
- **max_runtime**: ensure 3600s is set in DB (not in body, but verify)

## Integration

Part of the ticket audit pattern (`references/ticket-audit-pattern.md`).
Run after any bulk ticket creation or decomposition.
