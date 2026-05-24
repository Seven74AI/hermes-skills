# Dispatcher DB Corruption — Diagnosis and Recovery

## Architecture

Two levels of SQLite databases in the kanban system:

| File | Role | Contains |
|---|---|---|
| `/root/.hermes/kanban.db` | **Dispatcher coordination DB** | Scheduling state, dispatch queues — cache/coordination only |
| `/root/.hermes/kanban/boards/<board>/kanban.db` | **Board DB** | All task data: tasks, runs, events, comments, links, notify subs |

The board DBs hold the ground truth. The dispatcher DB is a coordination cache that can be safely recreated from scratch.

## Symptoms

Gateway log shows:
```
ERROR gateway.run: kanban dispatcher: board default database /root/.hermes/kanban.db 
is not a valid SQLite database; disabling dispatch for this board until the file changes 
or the gateway restarts.
```

The dispatcher stops dispatching tasks for that board. Other boards continue working if they have their own DBs.

## Diagnosis

```bash
# 1. Check if it's recognized as SQLite
file /root/.hermes/kanban.db
# Corrupted: "data"   Healthy: "SQLite 3.x database"

# 2. Hexdump the header — first 16 bytes should be "SQLite format 3\0"
hexdump -C /root/.hermes/kanban.db | head -1
# Corrupted example: 53 51 4c 69 74 17 03 03...  (bytes 5+ garbled)
# Healthy:           53 51 4c 69 74 65 20 66 6f 72 6d 61 74 20 33 00

# 3. Verify board DBs are healthy — if this works, data is safe
hermes kanban boards list

# 4. Check for WAL/SHM files (may have partial recovery data)
ls -la /root/.hermes/kanban.db /root/.hermes/kanban.db-wal /root/.hermes/kanban.db-shm
```

## Root cause

SQLite header corruption from an interrupted write. The process was killed (SIGKILL, OOM, host reboot) while SQLite was writing the header page. Bytes 0-4 ("SQLit") remain intact, but bytes 5-15 (the rest of the magic string + metadata) get overwritten with data from another page.

The `last modified` timestamp on the file tells you when it happened — typically an overnight unattended run.

## Recovery (zero data loss)

Board DBs contain everything. The dispatcher DB is empty/recreatable.

```bash
# 1. Keep a backup for forensics
mv /root/.hermes/kanban.db /root/.hermes/kanban.db.corrupted-backup

# 2. Also clean up any empty stub that may exist
rm -f /root/.hermes/kanban/kanban.db

# 3. Restart the gateway — it recreates the dispatcher DB on the first dispatch tick
# (systemd unit or manual restart)

# 4. Verify — after ~60s (dispatch interval), the DB appears
ls -la /root/.hermes/kanban.db
```

No `hermes kanban init` needed — that initializes board DBs, not the dispatcher DB.

## Verification

```bash
# Check no more errors
grep "not a valid SQLite" /root/.hermes/logs/gateway.log | tail -3

# Dispatcher should be spawning normally
grep "kanban dispatcher" /root/.hermes/logs/gateway.log | tail -3
```

## Why it goes unnoticed

The kanban dispatcher error is logged once per board at gateway startup, then the board is silently disabled. If watchdogs are configured "silent when clean" (most are), there's no alert. The board just stops spawning tasks — existing running tasks finish, new ones stay in `ready` indefinitely. The error can sit for days until someone checks the gateway logs directly.
