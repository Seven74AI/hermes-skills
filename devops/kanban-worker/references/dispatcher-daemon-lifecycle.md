# Dispatcher Daemon Lifecycle

The Kanban dispatcher runs **inside the gateway** (`hermes-gateway.service`) by default.
There is NO separate process — looking for a standalone daemon or systemd service is a dead end.

## Architecture

```
hermes-gateway.service
  └─ gateway.run()
       └─ embedded kanban dispatcher (every 60s per board)
```

Configured via `config.yaml`:
```yaml
kanban:
  dispatch_in_gateway: true      # default
  dispatch_interval_seconds: 60
  failure_limit: 2
```

## Standalone daemon (DEPRECATED)

`hermes kanban daemon` is deprecated and exits immediately with:

> hermes kanban daemon: DEPRECATED — the dispatcher now runs inside the gateway.

Use `--force` only if the gateway is unavailable (e.g. headless cron-only host).

## Checking if dispatcher is alive

```bash
systemctl is-active hermes-gateway    # dispatcher runs inside this
```

If the gateway is active, the dispatcher is running. No need to check for a separate process.

## Cycle

- **Interval**: 60 seconds between dispatch ticks (default, configurable via `dispatch_interval_seconds`)
- **Each tick**: scans all boards, finds `ready` tasks with valid assignees, spawns workers up to `max_spawn` per board
- **Failure limit**: 2 consecutive non-success runs (spawn_failed, timed_out, crashed) → task marked `gave_up`

## Common symptoms when dispatcher is failing

- Tasks in `ready` not being picked up for minutes/hours
- No new `claimed` / `spawned` events on any board
- `hermes kanban show <id>` shows `status: ready` but no recent runs
- **Check first**: `journalctl -u hermes-gateway --no-pager | grep -i "kanban dispatcher"` — if you see `tick failed on board <name>`, the dispatcher IS running but the DB is locked/corrupted

## Dispatcher DB lock recovery

Symptom: `hermes kanban stats` fails with `database is locked`, or gateway logs show repeated `kanban dispatcher: tick failed on board <name>` at `kanban_db.py line 1190` (`PRAGMA journal_mode=DELETE`).

The dispatcher DB (`/root/.hermes/kanban.db`) is a **coordination cache with zero critical data**. Board data lives in `/root/.hermes/kanban/boards/<slug>/kanban.db` and is never at risk.

Recovery:
```bash
# 1. Move the locked DB
sudo mv /root/.hermes/kanban.db /root/.hermes/kanban.db.corrupted-$(date +%Y%m%d_%H%M%S).bak

# 2. Restart the gateway — recreates kanban.db on next tick
sudo systemctl restart hermes-gateway

# 3. Verify dispatcher is ticking again
sleep 5
journalctl -u hermes-gateway --no-pager -n 20 | grep "kanban dispatcher"
```

Do NOT attempt recovery via `fuser` + `kill` first — if no process holds the file lock (verified with `fuser` returning empty), the DB itself is corrupt and must be replaced.

## Stale claim_lock after gateway restart

**Symptom**: after `systemctl restart hermes-gateway`, tasks sit in `ready` but `hermes kanban dispatch` shows `Spawned: 0` with no errors. Gateway logs show NO `tick failed` messages (dispatcher is running, DB is healthy, but no tasks are picked up).

**Root cause**: the old gateway process held `claim_lock` on ready tasks. When the gateway is restarted, the `claim_lock` field survives in the DB. The dispatch query filters `WHERE claim_lock IS NULL` — tasks with stale locks from the dead process are invisible. `release_stale_claims` has a TTL of `dispatch_stale_timeout_seconds` (default 4h), so the lock won't auto-clear for hours.

**Diagnosis**:

```bash
# 1. Run dry-run dispatch — if 0 spawns with no errors, suspect stale claim_lock
hermes kanban dispatch --dry-run

# 2. Check claim_lock on ready tasks
python3 -c "
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban.db')
rows = db.execute(\"SELECT id, status, claim_lock FROM tasks WHERE status='ready'\").fetchall()
for r in rows:
    print(f'{r[0]}: status={r[1]}, claim_lock={r[2]}')
"
# If claim_lock is a PID that doesn't exist anymore → stale lock
```

**Recovery**:

```python
import sqlite3
db = sqlite3.connect("/root/.hermes/kanban.db")
db.execute("UPDATE tasks SET claim_lock = NULL, claim_expires = NULL WHERE claim_lock IS NOT NULL")
db.commit()
db.close()
```

Then run `hermes kanban dispatch` to pick up the now-visible tasks.

**Two-phase failure**: a WAL-leaked DB (gateway logs show `tick failed … database is locked`) can mask a stale claim_lock underneath. After restarting the gateway to fix the WAL leak, always verify dispatch picks up tasks — a `Spawned: 0` after restart means the claim_lock is the second phase.

**Prevention**: use `hermes gateway restart` (the Hermes CLI) instead of raw `systemctl restart` — the CLI may handle claim_lock cleanup. If the gateway was SIGKILLed or crashed (not clean restart), stale claim_locks are guaranteed.

## Dispatch command (one-shot, manual)

```bash
hermes kanban dispatch           # one manual dispatch tick
hermes kanban dispatch --dry-run # preview only, no spawns
```
```
