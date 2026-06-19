# Kanban Claim System — Liveness Without Heartbeats

## The claim mechanism

When a worker is dispatched, it takes a **claim** (lock) on the task.
The claim has a TTL of `DEFAULT_CLAIM_TTL_SECONDS = 15 * 60` (15 minutes).

Every dispatcher tick (~60s), `release_stale_claims()` in `kanban_db.py` checks
for expired claims on `status='running'` tasks:

```
claim expired?
├─ PID alive on this host? → EXTEND claim (+15 min), emit claim_extended event (reason=pid_alive)
└─ PID dead or remote?     → RECLAIM task (status → ready for re-dispatch)
```

This is **independent of heartbeats**. Heartbeats are progress reports
from the worker; claims are liveness checks from the gateway. A worker
blocked in `process(action="wait")` cannot heartbeat, but its PID is
alive, so claims keep extending.

## Why this matters for the watchdog

The crash-loop watchdog (`check-crash-loops.py`) has a Phase 2b rule:

> running >1h AND no heartbeat >30min → auto-block

This produces false positives when a worker is correctly using
`background=true` + `process wait` for long transcription/build tasks.

**The fix:** before applying the no-heartbeat rule, check whether a
`claim_extended` event (reason=pid_alive) happened AFTER the last
heartbeat. If yes → worker is alive, skip.

```python
# In check-crash-loops.py Phase 2:
if last_claim > 0 and last_claim > last_hb:
    continue  # worker is alive — process wait is blocking heartbeats
```

## Claim extension cadence

Claims are extended when they EXPIRE, not on a fixed interval.
In practice this means claim_extended events are ~15 min apart,
but can be delayed by dispatcher load, DB locks, or gateway restarts.
Do NOT rely on claim extensions happening at a precise interval.

## Key distinction

| Signal | Who sends it | What it means |
|--------|-------------|---------------|
| `heartbeat` (`kanban_heartbeat`) | Worker agent loop | "I'm making progress" |
| `claim_extended` (pid_alive) | Gateway/dispatcher | "The worker PID is alive" |
| `claim` expiry + reclamation | Gateway/dispatcher | "The worker is dead — re-dispatch" |

The claim system is the **primary** liveness check. The watchdog is
a **secondary** safety net for edge cases the claim system misses
(remote workers, PID namespace issues, crash loops between dispatcher ticks).
