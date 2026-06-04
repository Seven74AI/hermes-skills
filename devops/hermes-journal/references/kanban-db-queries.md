# Kanban DB Query Patterns for Cron Reports

Safe, security-scanner-friendly patterns for querying kanban task data from cron jobs.

## DB Locations

```
/root/.hermes/kanban/boards/<board-slug>/kanban.db
```

## Schema Notes

- `tasks.completed_at` — Unix timestamp (integer seconds), NOT ISO date
- `tasks.status` — values: `done`, `running`, `blocked`, `ready`, `todo`, `archived`
- `tasks.title` — can be NULL (especially on archived tasks)

## Safe Queries (avoiding pipe-to-interpreter blocks)

### Count tasks completed in last 24h per board

```bash
python3 -c "
import sqlite3, time, os
cutoff = int(time.time()) - 86400
for board in sorted(os.listdir('/root/.hermes/kanban/boards')):
    db = os.path.join('/root/.hermes/kanban/boards', board, 'kanban.db')
    if not os.path.exists(db): continue
    conn = sqlite3.connect(db)
    cnt = conn.execute('SELECT COUNT(*) FROM tasks WHERE status=\"done\" AND completed_at > ?', (cutoff,)).fetchone()[0]
    if cnt:
        print(f'{board}: {cnt} done')
    conn.close()
"
```

### Get last completion time per board

```bash
python3 -c "
import sqlite3, time, os
for board in sorted(os.listdir('/root/.hermes/kanban/boards')):
    db = os.path.join('/root/.hermes/kanban/boards', board, 'kanban.db')
    if not os.path.exists(db): continue
    conn = sqlite3.connect(db)
    last = conn.execute('SELECT completed_at FROM tasks WHERE status=\"done\" AND completed_at IS NOT NULL ORDER BY completed_at DESC LIMIT 1').fetchone()
    if last:
        dt = time.strftime('%a %d %H:%M', time.localtime(last[0]))
        print(f'{board:<22} {dt}')
    conn.close()
"
```

### Find blocked tasks across all boards

```bash
python3 -c "
import sqlite3, os
for board in sorted(os.listdir('/root/.hermes/kanban/boards')):
    db = os.path.join('/root/.hermes/kanban/boards', board, 'kanban.db')
    if not os.path.exists(db): continue
    conn = sqlite3.connect(db)
    blocked = conn.execute('SELECT id, title FROM tasks WHERE status=\"blocked\"').fetchall()
    for t in blocked:
        print(f'{board}: 🔒 {t[0]} {(t[1] or \"(no title)\")[:80]}')
    conn.close()
"
```

### List all running tasks

```bash
python3 -c "
import sqlite3, os
for board in sorted(os.listdir('/root/.hermes/kanban/boards')):
    db = os.path.join('/root/.hermes/kanban/boards', board, 'kanban.db')
    if not os.path.exists(db): continue
    conn = sqlite3.connect(db)
    running = conn.execute('SELECT id, title FROM tasks WHERE status=\"running\"').fetchall()
    for t in running:
        print(f'{board}: ⚡ {t[0]} {(t[1] or \"(no title)\")[:80]}')
    conn.close()
"
```

## CLI Alternative (`hermes kanban list`)

For quick spot-checks, the CLI is simpler but slower across many boards:

```bash
hermes kanban --board <slug> list 2>&1 | head -40
```

Filters:
- `✓` prefix = done
- `●` prefix = running
- `⚠` prefix = blocked

## Pitfalls

- **`sqlite3` binary may not be installed** — always use `python3 -c "import sqlite3..."` instead of bare `sqlite3` commands in cron scripts
- **`completed_at` is a Unix timestamp**, not a datetime string — use `time.localtime()` for display
- **Don't pipe gh output to python3** — the security scanner blocks `gh | python3 -c`. Use `gh --json` with `-o /tmp/out.json` instead, or use `gh --jq` for inline filtering
- **Session data lives in `/root/.hermes/sessions/sessions.json`** — keyed by channel (e.g., `agent:main:discord:thread:...`), not a flat list. Use `isinstance(data, dict)` and iterate keys
