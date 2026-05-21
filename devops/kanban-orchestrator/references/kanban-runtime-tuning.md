# Kanban Runtime Tuning

How to diagnose and fix tasks that silently waste resources — timeout loops,
iteration budget exhaustion, and stuck workers the block watchdog can't see.

## The two timeout systems

Kanban workers have TWO independent timeout mechanisms:

### 1. Per-task `max_runtime_seconds` (DB column)

Stored in `tasks.max_runtime_seconds INTEGER`. Set at task creation via
`--max-runtime 600s`. Enforced by `enforce_max_runtime()` in kanban_db.py
— kills the worker subprocess when wall-clock time exceeds the limit.

**This is what the dispatcher actually enforces.** The profile's
`max_runtime_seconds` in config.yaml is a separate setting for
interactive sessions — kanban workers read the per-task DB column.

```
# Check current value:
python3 -c "
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
for r in db.execute('SELECT id, max_runtime_seconds FROM tasks WHERE status=\"running\"'):
    print(r)
db.close()
"

# Fix stuck tasks:
python3 -c "
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
db.execute('UPDATE tasks SET max_runtime_seconds = 600 WHERE id = \"t_xxxxx\"')
db.commit()
db.close()
"
hermes kanban --board <board> reclaim <task_id>
```

### 2. Profile `max_runtime_seconds` (config.yaml)

Set via `hermes config --profile <name> set max_runtime_seconds 600`.
Controls interactive session timeout. Does NOT propagate to kanban tasks
automatically — each task stores its own value in the DB.

**Pitfall:** Setting `max_runtime_seconds: 600` in the planner profile
and then creating a task assigned to `planner` does NOT give the task
600s. The task gets the default (NULL → some hardcoded fallback, likely
120s). ALWAYS set per-task runtime after creation.

## Iteration budget exhaustion (separate from timeouts)

`max_iterations` (default 50) limits API calls per worker run. When a
worker hits this limit, it exits cleanly — this is NOT a crash, so
`consecutive_failures` does NOT increment and the crash-loop watchdog
does NOT see it.

**Symptoms:**
- Task stays `running` for hours
- `hermes kanban runs <id>` shows `blocked → Iteration budget exhausted` repeatedly
- Worker processes are alive but making no progress
- Zero watchdog visibility

**Fix:**
```bash
hermes config --profile coder set kanban.max_iterations 120
hermes config --profile planner set kanban.max_iterations 120
```

**Known bug:** `consecutive_failures` stays 0 after timeout/killed outcomes.
The dispatcher's `_record_task_failure` may not increment the counter for
`timed_out` outcomes, or the counter gets reset on re-dispatch. This means
the crash-loop watchdog (threshold ≥5 consecutive_failures) is blind to
timeout loops — hence the need for the timeout-loop scanner below.

## Timeout-loop watchdog (check-crash-loops.py)

The crash-loop watchdog (`~/.hermes/scripts/check-crash-loops.py`) detects
THREE classes of stuck tasks:

### Phase 1 — Crash loops (existing)
`consecutive_failures >= 5` — OOM, segfault, worker PID vanished.

### Phase 2 — Timeout loops (NEW, 2026-05-20)
Uses a single pre-aggregated SQL query (JOIN with `GROUP BY`, not correlated
subqueries) to avoid O(n²) lookups on boards with 400+ task_runs. One pass
covers both sub-checks:

**2a: Excessive run count** — tasks with >20 total runs AND current run
age >30 min. The fresh-run filter prevents false positives on tasks that
were recently reclaimed and have historical runs but are now running fine.

**2b: Stale with no heartbeat** — tasks running >1h with no heartbeat
for >30min. Catches tasks stuck in long operations that haven't reported
progress.

### DB sync (NEW)
When Phase 2 detects a timeout loop (20+ runs), the watchdog directly
updates `consecutive_failures` in the DB: `SET consecutive_failures =
MIN(total_runs, 99) WHERE consecutive_failures < 5`. This patches the
kanban bug where timeout doesn't increment the counter, so Phase 1
detection works next cycle.

### Env vars
- `CRASH_LOOP_THRESHOLD=5` — min failures for Phase 1
- `AUTO_BLOCK=true` — auto-block on any detection

## Recovery workflow

1. Check what's actually running:
   ```bash
   python3 /root/.hermes/scripts/check-crash-loops.py
   ```

2. For tasks the watchdog flags as timeout loops:
   - Check actual runtime needed: `hermes kanban show <id> | grep elapsed`
   - Set appropriate `max_runtime_seconds` in DB
   - Set appropriate `max_iterations` in profile config
   - `hermes kanban reclaim <id>` to restart with new settings

3. If the dispatcher keeps overspawning workers despite `max_spawn`:
   See `references/max-spawn-overspawn-bug.md` — this is a known
   same-tick overspawn issue.

## Calibration defaults

| Task type | max_runtime_seconds | max_iterations |
|-----------|-------------------|----------------|
| Research / web-heavy | 600-1000s | 120 |
| Planning (large docs) | 600s | 120 |
| Code implementation | 300-600s | 90 |
| Review | 300s | 60 |
| Quick fix / small scope | 180s | 50 |

## Auto-fix monitor

For long-running boards where you want hands-off recovery, use the board monitor
script (`scripts/shop-monitor.py`). Runs in background, checks every 2 minutes,
applies auto-fixes, and stops when all tasks are done:

```bash
# Start monitoring (stops automatically when board is clean)
python3 ~/.hermes/skills/devops/kanban-orchestrator/scripts/shop-monitor.py <board> &

# Follow progress
tail -f /tmp/<board>-monitor.log
```

Auto-fixes applied:
- `max_runtime_seconds` NULL → 600s
- Worker PID dead → reclaim
- Stale heartbeat >30min + running >1h → reclaim
- High run count (>5) + stale → rt=600s + reclaim
- Blocked by timeout/budget/watchdog → unblock + reset failures

The script is generic — pass any board name as the first argument.
