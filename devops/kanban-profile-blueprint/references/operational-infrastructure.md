# Operational Cron Infrastructure

Active cron jobs for production kanban operations.

## Active jobs

| Job | Schedule | Type | Purpose |
|-----|----------|------|---------|
| Kanban Block Watchdog | every 5m | script+agent | `watchdog-all.py` wrapper: `check-blocked-tasks.py` handles crash retry with exponential backoff, `check-crash-loops.py` detects running tasks stuck in crash loops. Non-crash blocks passed to LLM for classification. |
| Disk Space Watchdog | every 10m | no_agent script | Checks disk usage. 50/60/70% → alert, 80%+ → triggers cleanup agent. |
| Disk Cleanup Agent | every 10m | agent | Receives watchdog output. Cleans old workspaces with guardrails: NEVER delete blocked/running/ready. |
| kanban workspace GC | every 15m | no_agent script | Deletes workspaces of tasks completed >5 min ago. Skips blocked/running/ready tasks. |

## Block Watchdog — Script auto-retry behavior

`check-blocked-tasks.py` now handles crash-blocked tasks autonomously:

**Crash detection**: tasks blocked via `gave_up` after crashes (exit_code, not alive) are classified as "crash-blocked."

**Exponential backoff schedule**:

| Retry # | Cooldown | Behavior |
|---------|----------|----------|
| #1 | 5 min | Unblock after 5 min since last crash |
| #2 | 10 min | Unblock after 10 min |
| #3 | 20 min | Unblock after 20 min |
| #4 | 40 min | Unblock after 40 min |
| #5 | 80 min | Last chance |
| #6+ | ∞ | MAX RETRIES EXCEEDED — escalate to user |

Retries are counted over a 24h sliding window. `consecutive_failures` is reset to 0 on each auto-unblock so the dispatcher's circuit breaker doesn't interfere.

**Never auto-unblocked**: review-required blocks, human-input blocks, and unknown block types — these are passed to the LLM for classification.

**LLM classification** (for non-crash blocks):
1. OK — legitimately blocked. Do NOTHING.
2. DEADLOCK — coder on review-required but reviewer done/archived. Unblock.
3. STALE — blocked >6h with no activity. Ping.
4. WATCHER CYCLE — watcher blocked >30 min. Unblock.

## Watchdog script location

All scripts in `~/.hermes/scripts/`:

| Script | Purpose |
|--------|---------|
| `watchdog-all.py` | Wrapper that runs both scanners below. Cron entry point. |
| `check-blocked-tasks.py` | Scans `--status blocked` tasks. Auto-retries crash-blocked. |
| `check-crash-loops.py` | Scans `running` tasks via direct SQLite. Phase 1: crash loops (fail ≥5). Phase 2a: timeout loops (runs ≥20). Phase 2b: stale tasks (>1h no hb). DB sync patches `consecutive_failures`. |
| `disk-watchdog.py` | Disk usage checker. |
| `kanban-gc-workspaces.py` | GC workspaces of done/archived tasks >5 min. |

## Crash-Loop Watchdog (`check-crash-loops.py`)

**Problem it solves:** The block watchdog only monitors `blocked` tasks. A task
in a silent crash loop (status stays `running`, dispatcher keeps respawning)
is completely invisible. Same for timeout loops where `max_runtime_seconds` is
too low — the worker times out every run but `consecutive_failures` stays 0
(kanban bug). Real case: shop board `t_fe9ad8a7` crashed 176 times over 3
hours; the-swarm planner timed out 401 times at 120s over 15 hours.

**Three detection phases:**

| Phase | Condition | Catches |
|-------|-----------|---------|
| 1 — Crash loops | `consecutive_failures >= 5` | segfault, OOM, protocol violation |
| 2a — Timeout loops | `total_runs >= 20` AND `current_run_age > 30 min` | `max_runtime_seconds` too low, timeout→respawn |
| 2b — Stale tasks | `running > 1h` AND `no heartbeat > 30 min` | silent worker death, no exit signal |

**DB sync:** When Phase 2a detects a timeout loop, it patches `consecutive_failures`
directly: `UPDATE tasks SET consecutive_failures = MIN(total_runs, 99)` so that
Phase 1 catches it next cycle.

**Fresh-run filter:** Phase 2a requires `current_run_age > 30 min` to avoid
false positives on tasks that were recently reclaimed and have historical runs
but are now running fine with corrected settings.

**Query optimization:** Uses a single `LEFT JOIN` with `GROUP BY` on `task_runs`
instead of per-row correlated subqueries. Completes in <5s even on boards with
400+ task_runs per task.

**Direct DB access** is necessary because `hermes kanban diagnostics` is slow
(30s+ timeout risk) and the dispatcher's `consecutive_failures` counter is
only in SQLite, not exposed via CLI output. Read pattern:

```python
db = sqlite3.connect(f'{KANBAN_BASE}/{board}/kanban.db')
rows = db.execute("""
    SELECT t.id, t.title, t.assignee, t.consecutive_failures,
           COALESCE(runs.run_count, 0) AS total_runs
    FROM tasks t
    LEFT JOIN (
        SELECT task_id, COUNT(*) AS run_count
        FROM task_runs GROUP BY task_id
    ) runs ON runs.task_id = t.id
    WHERE t.status = 'running'
      AND t.consecutive_failures < ?
    ORDER BY runs.run_count DESC
""", (threshold,)).fetchall()
```

**Environment variables:**
- `CRASH_LOOP_THRESHOLD=5` — min consecutive failures to trigger Phase 1 (default 5)
- `AUTO_BLOCK=true` — auto-block tasks exceeding any threshold

## Removed jobs (obsolete)

- **kanban-autoscale** — Removed. Fixed 4 role profiles.
- **Midnight Watchdog Reactivator** — Removed.

## Scripts

- `check-blocked-tasks.py` — Auto-retry crash tasks + output blocked tasks for LLM classification.
- `disk-watchdog.py` — Disk usage checker.
- `kanban-gc-workspaces.py` — GC workspaces of done/archived tasks >5 min.
