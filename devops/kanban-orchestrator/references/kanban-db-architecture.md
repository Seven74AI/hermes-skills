# Kanban DB Architecture & Disaster Recovery

## Two-tier architecture

The kanban system has TWO levels of SQLite databases:

| File | Role | Contains |
|---|---|---|
| `/root/.hermes/kanban.db` | Dispatcher coordination DB | Scheduling state, dispatch queues, mirrors of task data |
| `/root/.hermes/kanban/boards/<board>/kanban.db` | Per-board task DB | Source of truth: tasks, task_runs, task_events, task_comments, task_links, kanban_notify_subs |

The stale 0-byte `/root/.hermes/kanban/kanban.db` is a separate artifact — ignore it.

## What happens when the dispatcher DB is corrupted

Gateway log shows:
```
ERROR gateway.run: kanban dispatcher: board default database /root/.hermes/kanban.db is not a valid SQLite database; disabling dispatch for this board until the file changes or the gateway restarts.
```

Consequences:
- No new tasks dispatched — the dispatcher can't read its coordination DB
- Watchdogs (CI, block, pre-spawn) stop triggering
- Running tasks continue but get no siblings
- `ready` tasks stay queued indefinitely

Board DBs are unaffected. `hermes kanban boards list` still works because it reads per-board DBs directly.

## Diagnosing corruption

```python
data = open('/root/.hermes/kanban.db', 'rb').read()

# Check SQLite magic (should be "SQLite format 3\0" = 16 bytes)
expected = b'SQLite format 3\x00'
for i in range(16):
    if data[i] != expected[i]:
        print(f"Byte {i}: got 0x{data[i]:02x} expected 0x{expected[i]:02x}")

# Check if data exists beyond the header
for kw in [b'CREATE TABLE', b'INSERT INTO']:
    idx = data.find(kw)
    print(f"'{kw.decode()}' found at offset {idx}" if idx >= 0 else f"'{kw.decode()}' not found")
```

- `CREATE TABLE` found but `INSERT INTO` not found → schema exists, no data rows → safe to delete
- Both found → data exists, attempt recovery before deleting
- Neither found → file is garbage, safe to delete

## Recovery

### Option A: Delete and restart (recommended, zero data loss)

The dispatcher DB is a coordination cache. All real data lives in per-board DBs. When corrupted and data rows are absent (no `INSERT INTO` found):

```bash
rm /root/.hermes/kanban.db
hermes gateway restart
```

The gateway recreates it on startup. No task data is lost.

### Option B: Header fix (when INSERT INTO exists)

If the corruption is header-only and data rows exist in the binary, try:

```python
data = bytearray(open('/root/.hermes/kanban.db', 'rb').read())
correct_magic = b'SQLite format 3\x00'
data[:16] = correct_magic
open('/root/.hermes/kanban.db.fixed', 'wb').write(data)

import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban.db.fixed')
result = conn.execute('PRAGMA integrity_check').fetchall()
```

If integrity_check passes → replace the corrupted file and restart gateway.
If it fails with "file is not a database" → corruption goes deeper than the header → use Option A.

## Prevention

The corruption observed (2026-05-20) was likely a partial write during a process crash. The dispatcher DB is written to during dispatch operations; a kill -9 or OOM kill mid-write can corrupt the SQLite header.
