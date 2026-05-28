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

The dispatcher DB is at risk of corruption from:
- **Gateway crash mid-write** (kill -9, OOM, systemd stop timeout)
- **Module import failures at startup** (e.g. `ModuleNotFoundError: No module named 'yaml'`) causing repeated crash-restart cycles — each cycle risks corrupting the DB
- **WAL checkpoint race conditions** under heavy concurrent write load

### Permanent fix: DELETE journal mode (applied May 27, 2026)

The root cause of recurring corruption (May 25 + May 27) was WAL mode checkpoints
interrupted by unclean gateway shutdown. The fix replaces WAL with DELETE journal
mode across ALL kanban DBs:

**Code change in `hermes_cli/kanban_db.py` (line ~1184):**
```python
# Force DELETE journal mode for kanban DBs.
# WAL mode is fast but vulnerable to checkpoint corruption on
# unclean shutdown (PRAGMA integrity_check failures after crash).
# DELETE mode writes every transaction directly to the main DB —
# no WAL file to desynchronise. Slightly more I/O, but kanban
# write volume is low (a few writes/min) so the cost is noise.
conn.execute("PRAGMA journal_mode=DELETE")
conn.execute("PRAGMA synchronous=FULL")
```

**Convert existing DBs:**
```bash
python3 -c "
import sqlite3, os
for path in ['/root/.hermes/kanban.db'] + glob.glob('/root/.hermes/kanban/boards/*/kanban.db'):
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('PRAGMA synchronous=FULL')
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    for ext in ['-wal', '-shm']:
        f = path + ext
        if os.path.exists(f): os.remove(f)
    conn.close()
"
```

**Verification:** After gateway restart, ALL DBs should show `journal_mode=delete` and `synchronous=2` (FULL).

### Integrity watchdog

A cron watchdog runs hourly and checks ALL kanban DBs with `PRAGMA integrity_check`.
Silent when clean, alerts Discord + Telegram on corruption.

- Script: `~/.hermes/scripts/kanban-integrity-watchdog.py`
- Cron: `b568a8418cf3` — `0 * * * *`, no_agent=true
- Deliver: Discord #ops + Telegram

If the watchdog fires: the DB is corrupted. Follow the recovery procedure below
IMMEDIATELY — don't wait for the gateway to auto-recover and lose data.

### Recurring corruption pattern (observed May 25 + May 27, 2026)

The corruption is self-reinforcing across gateway restarts:

1. Gateway crashes uncleanly → DB corrupted
2. Gateway auto-recovers by creating a fresh DB (0 rows)
3. All tasks, runs, events, and notify subscriptions are lost
4. **Workers spawned BEFORE the corruption survive as orphans** — they keep running but the dispatcher forgets them
5. The next gateway crash repeats the cycle

**Evidence from May 27, 2026:**
- Corruption detected at 01:28:25 (`database disk image is malformed`)
- 234 consecutive errors over 20 minutes
- Gateway rebuilt DB at 01:48:10 → 0 tasks, 0 runs, 0 events
- Worker PID 989572 for `t_38f28120` (spawned at 00:59) survived — kept running orphaned
- Default board DB (`/root/.hermes/kanban/kanban.db`) was already empty from the May 25 corruption

### Backup files

Before rebuilding, the gateway creates backups of the corrupted DB:
- `kanban.db.corrupted-backup` — last pre-rebuild state
- `kanban.db.corrupt.<timestamp>.bak` — timestamped snapshot
- `kanban.db.fixed` — from a previous recovery (may be stale)

**These backups CONTAIN the lost data** — 54 tasks, 401 events, 64 task runs in the May 27 case.

### Recovery from backup

When a corruption has wiped the dispatcher DB but the backup exists:

```python
import sqlite3, os, time

corrupted = '/root/.hermes/kanban.db.corrupted-backup'  # or .corrupt.<ts>.bak
src = sqlite3.connect(corrupted)
src.row_factory = sqlite3.Row

# 1. Probe — which tables are readable?
for table in ['tasks', 'task_runs', 'task_events', 'task_comments', 'task_links', 'kanban_notify_subs']:
    try:
        n = src.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        print(f'{table}: OK ({n} rows)')
    except sqlite3.DatabaseError as e:
        print(f'{table}: CORRUPTED — {e}')

# 2. Extract readable tables
data = {}
for table in ['tasks', 'task_runs', 'task_events', 'task_comments', 'task_links']:
    try:
        rows = [dict(r) for r in src.execute(f'SELECT * FROM {table}')]
        data[table] = rows
    except:
        print(f'{table}: skipped (corrupted)')
src.close()

# 3. Rebuild fresh DB
os.rename('/root/.hermes/kanban.db', '/root/.hermes/kanban.db.pre-restore')
dst = sqlite3.connect('/root/.hermes/kanban.db')
dst.executescript(SCHEMA_SQL)  # from kanban_db.py or recreate manually
for table, rows in data.items():
    if not rows: continue
    cols = list(rows[0].keys())
    ph = ','.join(['?' for _ in cols])
    cn = ','.join(cols)
    for row in rows:
        dst.execute(f'INSERT OR REPLACE INTO {table} ({cn}) VALUES ({ph})',
                   [row[c] for c in cols])
dst.commit()

# 4. Fix running tasks — reclaim orphaned workers
for r in dst.execute("SELECT id, worker_pid FROM tasks WHERE status='running'").fetchall():
    if r['worker_pid']:
        try: os.kill(r['worker_pid'], 0)
        except OSError:
            dst.execute("UPDATE tasks SET status='ready', claim_lock=NULL, worker_pid=NULL, current_run_id=NULL WHERE id=?", (r['id'],))
            dst.execute("UPDATE task_runs SET status='crashed', outcome='crashed', ended_at=? WHERE task_id=? AND status='running'", (int(time.time()), r['id']))
dst.commit()

# 5. Verify
r = dst.execute('PRAGMA integrity_check').fetchone()
print(f'Integrity: {r[0]}')
dst.close()
```

**After recovery:**
1. `hermes gateway restart` — dispatcher picks up the restored tasks
2. Check `hermes kanban boards list` — tasks should appear
3. Re-run integrity watchdog: `python3 ~/.hermes/scripts/kanban-integrity-watchdog.py`

### Recovery from backup (quick — for when data is intact)

**For running workers:** Check `ps aux | grep 'hermes.*kanban'` — if workers exist but no tasks in the dispatcher, they're orphans. Kill them and recreate their tickets from the backup.

### Board DB isolation

Each board's DB lives at `/root/.hermes/kanban/boards/<slug>/kanban.db`. The **default board** is special — it uses the root-level `/root/.hermes/kanban/kanban.db` (not a subdirectory). When this file is wiped (4 KB, 0 tables), the default board becomes empty but still shows in `hermes kanban boards list`.
