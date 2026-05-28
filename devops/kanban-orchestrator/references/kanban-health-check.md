# Kanban Health Check — Diagnostic Workflow

Quick board-wide health check to identify stale claims, stuck workers, DB corruption, and real active work. Use this when the user asks "what teams are working?" or you suspect silent failures.

## Step 0 — DB integrity (ALWAYS FIRST)

A corrupted dispatcher DB will silently disable dispatch for affected boards with no alert. Always check integrity before anything else:

```bash
python3 /root/.hermes/scripts/kanban-integrity-watchdog.py
```

Silent exit (0) = all clean. Non-zero = corruption detected (backup auto-saved as `<path>.corrupt.<ts>.bak`).

**⚠️ If corruption found:** Do NOT proceed with normal health check or dispatch. Follow `references/kanban-db-corruption-recovery.md` instead. Corrupted DBs can lose tasks silently (real case: 2026-05-27 — 54 tasks vanished when dispatcher DB was rebuilt from scratch).

**⚠️ Pitfall — silent corruption:** The gateway auto-heals corrupted DBs by recreating them EMPTY. It backs up the corrupt file as `kanban.db.corrupted-backup` first, but does not restore data. If you don't check integrity proactively, you may discover missing tasks days later when the user asks "where are my tickets?"

## Step 1 — Board overview

```bash
hermes kanban boards list
```

Look at the COUNTS column. Boards with `running=N` or `blocked=N` need investigation. Boards with only `done` and `archived` are idle.

## Dashboard access (web UI)

The web dashboard runs on port 9119. First launch does `npm ci` + `npm run build` (~30s), subsequent starts are instant with `--skip-build`.

```bash
# Local only
hermes dashboard

# Tailscale / remote access — bind to all interfaces
hermes dashboard --host 0.0.0.0 --insecure --skip-build
```

Access via Tailscale IP (e.g. `http://100.122.244.70:9119`). Use `--stop` and `--status` to manage.

## Step 2 — List running tasks per board

For each board with `running>0`:

```bash
hermes kanban --board <slug> list --status running
```

**⚠️ Pitfall:** `--board` goes BEFORE `list`, not after. `hermes kanban list --board <slug>` fails with "unrecognized arguments." Same for all kanban subcommands.

**⚠️ Pitfall:** `--status` takes exactly ONE value. `--status running,todo` fails. Make separate calls for each status.

## Step 3 — Inspect task details (events, runs, PIDs)

For each running task, get the full history:

```bash
hermes kanban --board <slug> show <task_id>
```

Key fields in the output:
- **Events:** shows claim, spawn, heartbeat, block, complete events in chronological order
- **Runs:** each run has a status (`active`, `completed`, `blocked`) and duration
- Look for `spawned {'pid': <N>}` in events to get the worker PID

## Step 4 — Verify worker liveness

```bash
ps -p <pid> -o pid,stat,etime,cmd --no-headers
```

- **PID exists, stat shows `S` or `R`** → worker is alive and actively working
- **PID not found** → worker died. Check run status:
  - If last run is `completed` → stale claim (watchdog should catch this)
  - If last run is `active` with no completion → crashed worker

## Step 5 — Check diagnostics

```bash
hermes kanban --board <slug> diagnostics
```

Shows crash alerts (repeated_crashes, OOM kills). These produce dashboard badges and are tracked separately from run status.

## Interpreting results

| Run status | PID | Meaning |
|---|---|---|
| `active` | alive | ✅ Worker is working |
| `active` | dead | ❌ Crashed silently — needs reclaim |
| `completed` | dead | ⚠️ Stale claim — worker finished but didn't call `kanban_complete` |
| `blocked` | dead | ⚠️ Worker blocked itself (review-required, budget, etc.) — check reason |
| `blocked` | alive | ⏳ Worker waiting for human action |

## The Watchdog's role

The Kanban Block Watchdog (cron job `7ad8ddd5b9c9`, runs every 5 min) handles stale claims automatically:
- Reclaims `running` tasks with dead workers whose last run completed
- Classifies `blocked` tasks: technical failures (crash/OOM/budget) → auto-unblock; review-required → leave alone
- Spawns new tasks via dispatch after cleanup

If you suspect stale claims but the watchdog hasn't run yet, trigger it manually:
```bash
hermes cron run 7ad8ddd5b9c9
```

Then re-run the health check from Step 1 to see the cleaned state.

## Quick one-liner: active workers summary

```bash
for board in $(hermes kanban boards list 2>/dev/null | awk '/^  /{print $1}'); do
  hermes kanban --board "$board" list --status running 2>/dev/null | grep '●' | while read -r line; do
    tid=$(echo "$line" | awk '{print $2}')
    assignee=$(echo "$line" | awk '{print $NF}')
    pid=$(hermes kanban --board "$board" show "$tid" 2>/dev/null | grep -oP 'spawned.*pid.*?\K\d+' | tail -1)
    alive=$(ps -p "$pid" -o pid= 2>/dev/null || echo "DEAD")
    echo "$board/$tid | $assignee | PID=$alive"
  done
done
```

This produces a table of every running task across all boards with its worker PID status — the fastest way to answer "what's actually working right now?"
