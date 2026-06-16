# Kanban Board Recovery — After Dispatcher Auto-Disable

The kanban dispatcher auto-disables a board when it detects `kanban.db is not a valid SQLite database`. The gateway log contains the exact message:

```
ERROR gateway.run: kanban dispatcher: board <name> database <path> is not a valid SQLite database; disabling dispatch for this board until the file changes or the gateway restarts.
```

## The Problem

The auto-re-enable condition ("file changes or gateway restarts") may never trigger if the corruption was transient (e.g., a gateway crash/restart mid-write, or temporary I/O error). Hours later the DB passes `PRAGMA integrity_check` but the board stays disabled because:

1. The DB file modification time did not change after the transient corruption resolved
2. The gateway has long uptime (21+ days) and hasn't restarted

Example: knowledge-base board, 2026-06-14 22:06. DB was 3.7 MB, integrity_check passed hours later, but board remained disabled because the file mtime was still 22:06 and the gateway never restarted.

## Recovery Procedure

### Step 1: Verify DB integrity

```bash
sqlite3 /root/.hermes/kanban/boards/<board>/kanban.db "PRAGMA integrity_check;"
```

Expected output: `ok`. If the output is anything else (errors, corruption messages), the DB needs to be restored from backup or recreated with `hermes kanban init`.

### Step 2: Re-enable the board

**Option A — Touch the file (fastest, no disruption):**

```bash
touch /root/.hermes/kanban/boards/<board>/kanban.db
```

The dispatcher detects the mtime change on its next tick (~60 seconds) and re-enables the board automatically. No gateway restart needed.

**Option B — Bounce the gateway (nuclear, takes ~10s):**

```bash
sudo systemctl restart hermes-gateway
```

This re-reads all board databases on startup and clears the disabled state. Use this if touching the file doesn't work or if multiple boards need re-enablement simultaneously.

### Step 3: Verify re-enablement

Check that the board is accepting dispatch by listing active tasks or checking gateway logs:

```bash
# Should show tasks without "board disabled" errors
hermes kanban --board <board> list

# Gateway log should no longer show "disabling dispatch" for this board
journalctl -u hermes-gateway --since "2 minutes ago" | grep "<board>"
```

## Prevention

The **Kanban DB Integrity Watchdog** cron (`b568a8418cf3`) should be extended to:
1. Run `PRAGMA integrity_check` on all board DBs
2. If a board passed integrity but the dispatcher log shows it was disabled, auto-touch the file
3. Alert if a board failed integrity (needs restore/recreation)

This watchdog currently exists but does not perform the re-enable step — it only reports corruption status.
