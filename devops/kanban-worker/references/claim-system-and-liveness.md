# Claim System & Liveness Detection

## How claims work

When a worker is dispatched, it takes a **claim** (lock) on the task. Default TTL: 15 minutes (`DEFAULT_CLAIM_TTL_SECONDS`).

Every dispatcher tick, `release_stale_claims()` checks for expired claims:
- If the worker PID is alive (`_pid_alive`) → extend claim by another 15 min, emit `claim_extended` event with `reason=pid_alive`
- If the worker PID is dead → reclaim task to `ready`

Claims are independent of heartbeats. Heartbeats are progress reports; claims are OS-level liveness checks. A worker blocked on `process wait` cannot heartbeat, but the claim keeps getting extended because the PID is alive.

Code: `hermes_cli/kanban_db.py:2510-2577`

## Claim extension intervals

Claims are extended when they expire (~15 min), not every few seconds. The actual interval depends on dispatcher tick timing. In practice: 15-20 min is normal, but can spike to 30+ min under load. Claim extensions happen in the gateway's dispatcher tick, not in the worker process.

## Watchdog vs claims

The kanban block watchdog (`check-crash-loops.py`) originally only checked `last_heartbeat_at` to detect stuck workers. This caused false positives: a worker doing `process wait` for 20 min transcription has zero heartbeats but is alive.

**Fix applied (2026-06-18):** Before flagging a task for "no heartbeat," check if `last_claim_ext > last_heartbeat`. If the claim was extended after the last heartbeat, the gateway confirmed via `pid_alive` that the worker is alive — skip.

```python
if last_claim > 0 and last_claim > last_hb:
    continue  # worker is alive, skip
```

This is timing-independent: any claim extension is proof of life, regardless of how long ago it happened.

## Claim vs heartbeat in the event log

- `claimed` — task was claimed by a worker (assigned a PID)
- `claim_extended` — claim TTL was extended because PID was alive (reason: `pid_alive`)
- `heartbeat` — worker sent a progress report (optional, not needed for liveness)

A task with claim_extended events and no heartbeats is a worker in `process wait` — healthy, not stuck.
