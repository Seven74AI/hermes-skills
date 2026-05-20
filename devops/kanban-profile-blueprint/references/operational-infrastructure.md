# Operational Cron Infrastructure

Active cron jobs for production kanban operations.

## Active jobs

| Job | Schedule | Type | Purpose |
|-----|----------|------|---------|
| Kanban Block Watchdog | every 5m | script+agent | `check-blocked-tasks.py` handles crash retry automatically with exponential backoff. Non-crash blocks passed to LLM for classification (review deadlocks, stale blocks, watcher cycles). |
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

`~/.hermes/scripts/check-blocked-tasks.py`

The script uses kanban DB events (JSON format with `kind` and `payload` fields) to detect crash history and count retries.

## Removed jobs (obsolete)

- **kanban-autoscale** — Removed. Fixed 4 role profiles.
- **Midnight Watchdog Reactivator** — Removed.

## Scripts

- `check-blocked-tasks.py` — Auto-retry crash tasks + output blocked tasks for LLM classification.
- `disk-watchdog.py` — Disk usage checker.
- `kanban-gc-workspaces.py` — GC workspaces of done/archived tasks >5 min.
