# Disk-Full → SQLite WAL Corruption → Kanban Board Disable

Full incident pattern from 2026-07-13 on music-library board. Disk filled to 100%, causing a cascading failure that self-recovered after space was freed.

## Cascade Timeline

```
00:09  Disk hits 100% (112M free of 96G) — watchdog fires CRITICAL
       Disk oscillates between 88-98% for hours as GC and workers compete
03:55  Dockerd: "no space left on device" — Docker container log writes fail
       This is ~1 hour BEFORE kanban.db corruption — an early warning signal
04:47  Dispatcher: "kanban.db is not a valid SQLite database"
       Board music-library disabled — no new tasks dispatched
05:05  Dispatcher: "kanban dispatcher stuck: ready queue non-empty, 0 workers spawned"
05:48  Dispatcher: board still disabled (re-detects invalid DB)
~06:00 Disk frees up (GC removes old workspaces)
06:05  Disk at 81% — WAL checkpoint succeeds, DB self-recovers
06:06  DB validated as SQLite 3.x, 2.4M — board operational again
       Workers re-dispatched normally
```

## Root Cause

SQLite in WAL mode writes to both the main database file AND a separate WAL file. When disk is full:
1. WAL writes fail with I/O errors
2. The main DB file becomes inconsistent (WAL not checkpointed)
3. Next read attempt fails SQLite integrity check
4. Dispatcher reads kanban.db → detects invalid header → disables board

## Recovery

**Self-recovery (what happened):** Once disk space was freed, the WAL checkpoint succeeded on the next SQLite open, restoring the DB to a consistent state. No manual intervention needed.

**Manual recovery (if self-recovery fails):**
1. Free disk space first (see workspace cleanup below)
2. Check if DB is recoverable: `sqlite3 /path/to/kanban.db "PRAGMA integrity_check"`
3. If integrity check fails, try: `sqlite3 /path/to/kanban.db ".recover" | sqlite3 /path/to/kanban_recovered.db`
4. Replace the corrupted DB: `mv /path/to/kanban_recovered.db /path/to/kanban.db`
5. Touch the board.json to trigger re-enable: the dispatcher watches for file changes
6. If unrecoverable: `hermes kanban --board <name> init` (destroys board, creates fresh)

## Emergency Disk Cleanup

When disk is critical (< 5G free) and the GC cron isn't fast enough:

```bash
# 1. Kill non-essential kanban workers to stop workspace creation
pkill -f "kanban task" --signal STOP  # SIGSTOP, not kill — preserves state

# 2. Remove scratch workspaces of done/archived tasks immediately
#    (GC has 5-min delay — skip it during emergency)
find /root/.hermes/kanban/boards/*/workspaces/ -maxdepth 1 -type d \
  -name "t_*" -mmin +1 -exec rm -rf {} \; 2>/dev/null

# 3. Truncate large log files
truncate -s 0 /var/log/syslog  # if > 500M
journalctl --vacuum-size=200M

# 4. Clear Docker build cache
docker system prune -af --volumes 2>/dev/null

# 5. Resume workers
pkill -f "kanban task" --signal CONT
```

## Prevention

- **Keep disk below 80%.** Once you hit 85%, the cascade to 100% can happen in < 2 hours with multiple kanban workers cloning repos.
- **Treat CLEANUP_TRIGGER as immediate action item.** The disk watchdog fires at 75%. Don't wait for the cleanup agent — it may be paused or saturated.
- **Monitor Docker log errors.** "no space left on device" in dockerd logs is a 1-hour early warning before SQLite corruption. Grep for it in cron scripts or alert on it.
- **Workspace GC cron must be healthy.** Job `eb1ab33f9bf4` (every 15m) is the primary defense. If it's ever missing: `hermes cron create --name "kanban workspace GC" --schedule "every 15m" --script kanban-gc-workspaces.py --no-agent --deliver local`
- **Each scratch workspace is 1.5-2.7 GB.** With 25+ active/done workspaces unpurged, that's 40+ GB. The 5-minute GC delay is normally safe but becomes a problem when workers spawn faster than GC cleans.
