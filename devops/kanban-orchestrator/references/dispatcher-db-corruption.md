# Dispatcher DB Corruption — Full Diagnosis & Recovery

The dispatcher DB (`/root/.hermes/kanban.db`) is a SQLite coordination cache
in WAL mode. All real task data lives in per-board DBs (`boards/<slug>/kanban.db`).
When the dispatcher DB corrupts, the gateway loses track of dispatched workers
but board data remains intact.

## Corruption causes (certain, not probable)

The only certain cause observed: **unclean gateway shutdown during a WAL
checkpoint or active write.** On `systemctl stop` with a stuck worker, systemd
sends SIGTERM → 90s timeout → SIGKILL. If SQLite is mid-write when the
SIGKILL hits, page-level corruption can occur.

Triggering events observed:
- Gateway crash-loop (`ModuleNotFoundError`, `yaml` missing, etc.) — 4 restarts in 17s
- Gateway SIGKILL after drain timeout
- Does NOT happen on clean `hermes gateway restart`

## Latent corruption pattern

Corrupted pages may not be read for days. The DB passes `sqlite3.connect()`
and normal queries until a read finally hits a damaged page. At that point:

```
WARNING gateway.run: kanban notifier tick failed: database disk image is malformed
```

This repeats every 5s (the notifier tick interval). The dispatcher may also
start failing. Workers spawned BEFORE the corrupted page was hit continue
running as **orphans** — they appear in `ps aux` but no longer have task
records in any DB.

## Diagnosis

### Step 1 — Check if corruption is in dispatcher DB or a board DB

```bash
# Corrupted dispatcher DB — fails integrity_check
python3 -c "
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban.db')
print(db.execute('PRAGMA integrity_check').fetchall())
db.close()
"
```

Board DBs are independently healthy. Check specific boards:
```bash
for db in /root/.hermes/kanban/boards/*/kanban.db; do
  board=$(basename $(dirname $db))
  result=$(python3 -c "
import sqlite3
db = sqlite3.connect('$db')
print(db.execute('PRAGMA integrity_check').fetchone()[0])
" 2>&1)
  echo "$board: $result"
done
```

### Step 2 — Check gateway logs for the corruption timeline

```bash
journalctl -u hermes-gateway --since "YYYY-MM-DD HH:00" --no-pager | grep -E "malformed|corrupt|no such table"
```

Key phases in the log:
1. First occurrence: `database disk image is malformed` — corruption detected
2. After ~20 min: `no such table: kanban_notify_subs` — gateway auto-rebuilt
3. Backup files appear at `~/.hermes/kanban.db.corrupted-backup` during recovery

### Step 3 — Find orphan workers

Workers spawned before corruption survive. They have no backing task anymore:

```bash
ps aux | grep "hermes.*kanban.*task" | grep -v grep
```

Kill them with SIGKILL if needed:
```bash
kill -9 <PID>
```

### Step 4 — Cross-reference with previous corruptions

Check the backup chain:
```bash
ls -la /root/.hermes/kanban.db*
# Typical: kanban.db (current), kanban.db.corrupted-backup (pre-recovery),
# kanban.db.corrupt.<timestamp>.bak (older), kanban.db.fixed (oldest)
```

If `.fixed` exists and is larger than the current DB, the DB has been
corrupted and recovered multiple times — latent damage from the first crash
may have been incompletely repaired.

## Recovery

### Option A: Let gateway auto-recover (happens automatically)

The gateway detects corruption, creates a backup, rebuilds from scratch.
All coordination state is lost but board DBs are fine. New tasks dispatch normally.

### Option B: Extract data from corrupted backup

Even when `PRAGMA integrity_check` fails, Python `sqlite3` may still read
intact pages. The backup at `.corrupted-backup` is the last known state:

```python
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban.db.corrupted-backup')
# List all tables and row counts
for table in ['tasks', 'task_runs', 'task_events', 'task_comments', 'task_links',
              'kanban_notify_subs']:
    try:
        n = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        print(f'{table}: {n} rows')
    except Exception as e:
        print(f'{table}: CORRUPTED — {e}')

# Find a specific task
task = db.execute("SELECT * FROM tasks WHERE id = 't_38f28120'").fetchone()
db.close()
```

### Option C: Manual rebuild

```bash
# Backup the corrupted file
cp /root/.hermes/kanban.db /root/.hermes/kanban.db.bak

# Remove and let gateway recreate on next tick
rm /root/.hermes/kanban.db
# Gateway auto-creates on next notifier/dispatcher tick
# OR restart:
hermes gateway restart
```

## Prevention

- **WAL mode with `synchronous=NORMAL`** — already set by `connect()`. This is the
  best SQLite can do; corruption from SIGKILL is inherent to any non-FULL sync.
- **Avoid SIGKILL** — use `hermes gateway stop` (SIGTERM, clean shutdown) rather
  than `kill -9` or `systemctl kill`.
- **Monitor orphan workers** — if `ps aux | grep kanban.*task` shows workers but
  the board shows 0 running, the dispatcher DB may be corrupted.
- **Backup dispatcher DB** — the quick-backup cron already captures critical state.

## Pitfalls

- **Python can open a corrupted DB but integrity_check fails.** `sqlite3.connect()`
  reads the header and schema; damaged pages are only detected on actual read.
  Always run `PRAGMA integrity_check` when a DB acts suspiciously.
- **The backup IS corrupted but still readable for data extraction.**
  `integrity_check` may fail on the backup too, but intact pages yield valuable data.
- **Orphan workers keep consuming CPU/RAM.** A worker spawned with PID 989572
  and no backing task will happily transcribe for 7 hours with no output file.
  Always `ps aux | grep kanban.*task` after a corruption event.
- **board DBs are independent.** Corrupting the dispatcher DB does NOT touch
  board data. Don't delete board DBs as part of recovery.
- **Gateway log shows "malformed" for the NOTIFIER, not the dispatcher.**
  The error source is `_kanban_notifier_watcher` reading from a board DB,
  but the root cause can be the dispatcher DB if `list_board_slugs()` or
  subscription tables live there. Always check both.
- **Correlation ≠ causation.** When "malformed" appears shortly after a
  Telegram/Discord notification error, the DB was already corrupted —
  the notification error just happened to trigger the read that found it.
