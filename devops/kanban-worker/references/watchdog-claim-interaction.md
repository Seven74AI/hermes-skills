# Watchdog vs Claim System — False Positives During `process wait`

## The problem

`process(action="wait")` blocks the agent loop entirely — the worker can't send
heartbeats. The Block Watchdog's Phase 2b rule flags any task running >1h with
no heartbeat >30min as "stuck" and auto-blocks it.

But the worker IS alive — the kanban claim system proves it.

## How the claim system works

```
DEFAULT_CLAIM_TTL = 15 minutes
```

When a worker is dispatched, it takes a **claim** (lock) on the task with a
15-minute TTL. Every dispatcher tick, `release_stale_claims()` checks expired
claims:

- **PID alive?** → extends the claim for another 15 min. Logs a
  `claim_extended` event with `reason: pid_alive`.
- **PID dead?** → reclaims the task (status → `ready`) for re-dispatch.

This is a kernel-level liveness check, **independent of heartbeats**. Heartbeats
are progress reports; claims are survival checks. `process wait` blocks
heartbeats but the PID stays alive → claims keep extending.

Key code (kanban_db.py:2542):
```python
if host_local and row["worker_pid"] and _pid_alive(row["worker_pid"]):
    new_expires = now + _resolve_claim_ttl_seconds()  # extend
    # ... claim_extended event with reason="pid_alive"
```

## The fix: `claim > hb`

The watchdog must check for recent claim extensions before flagging a task:

```python
# If the gateway confirmed the PID is alive AFTER the last heartbeat,
# the worker is just blocked on process wait. Skip.
if last_claim > 0 and last_claim > last_hb:
    continue  # worker is alive
```

This is **independent of timing** — it doesn't matter if the claim was extended
5 minutes ago or 15 minutes ago. If it happened after the last heartbeat, the
gateway vouches for the worker's life.

Applied in `check-crash-loops.py` (2026-06-18).

## Claim extension intervals

Empirical data from 319 intervals across all boards:
- ~55% are 15-20 minutes (normal dispatcher tick)
- ~45% are >20 minutes (dispatcher delayed by DB lock, system load, etc.)
- Max observed: 14.6 hours (gateway restart)

This variability is why a flat time threshold (e.g., "claim within 5 min") fails.
The `claim > hb` comparison eliminates the timing dependency entirely.

## Verification

To check whether a blocked task was a false positive, compare the claim and
heartbeat timestamps AT THE TIME OF BLOCK (not current DB state, which reflects
post-recovery runs):

```sql
-- Last heartbeat BEFORE the block
SELECT MAX(created_at) FROM task_events
WHERE task_id = ? AND kind = 'heartbeat' AND created_at < <block_time>;

-- Last claim_extended BEFORE the block
SELECT MAX(created_at) FROM task_events
WHERE task_id = ? AND kind = 'claim_extended' AND created_at < <block_time>;
```

If `claim > hb` at block time, the auto-block was a false positive.

## What still catches genuinely stuck workers

- **Claim reclaim:** If the worker PID dies, the next dispatcher tick (≤15 min)
  reclaims the task.
- **`max_runtime_seconds`:** The gateway enforces a hard runtime cap (3600s for
  KB tickets). Expired tasks are killed regardless of claim status.
- **Phase 2a:** The watchdog still catches `>20 total runs + >30min runtime`
  even with live claims — this catches genuine crash-loops where the dispatcher
  keeps respawning a broken worker.
