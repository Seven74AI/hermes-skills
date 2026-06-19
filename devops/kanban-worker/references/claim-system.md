# Kanban Claim System

How the Kanban dispatcher tracks worker liveness — separate from heartbeats.

## Mechanism

When a worker is dispatched, it takes a **claim** (lock) on the task:

```
kanban_db.py — DEFAULT_CLAIM_TTL_SECONDS = 15 * 60  # 900s
```

Every ~15 minutes, the gateway's `release_stale_claims()` runs. For each task whose
claim has expired:

1. **PID alive?** → extend the claim for another 15 min. Writes a `claim_extended`
   event with `reason: "pid_alive"`. The worker is undisturbed.
2. **PID dead?** → reclaim the task (status → `ready`), kill any orphans.

The kernel code (kanban_db.py:2542):

```python
if host_local and row["worker_pid"] and _pid_alive(row["worker_pid"]):
    new_expires = now + _resolve_claim_ttl_seconds()  # +900s
    # → claim_extended event with reason="pid_alive"
    continue
# else: reclaim → ready
```

The design rationale (from the code comment):

> *"Reclaiming a live worker mid-flight produces the spawn-then-immediately-reclaim
> loop seen on slow models that spend longer than DEFAULT_CLAIM_TTL_SECONDS inside
> a single tool-free LLM call — no tool calls means no heartbeat, even though the
> subprocess is healthy."*

## Claims vs Heartbeats

| | Claim extensions | Heartbeats |
|---|---|---|
| **Who** | Gateway (kernel) | Worker (agent) |
| **Trigger** | PID alive check every ~15 min | Explicit `kanban_heartbeat()` call |
| **What it means** | "Worker process exists" | "Worker is making progress" |
| **Available during `process wait`** | ✅ Yes — PID is alive | ❌ No — agent loop blocked |

**The claim extension IS the real liveness signal.** Heartbeats are progress
reports. When `process wait` blocks the agent loop, heartbeats stop — but the
PID is alive, so claim extensions continue.

## Watchdog interaction

The `check-crash-loops.py` watchdog (Phase 2b) originally checked ONLY
`last_heartbeat_at`:

```
# ❌ Old — false positive when process wait blocks heartbeats
if age_run > 3600 and age_hb > 1800:
    auto_block("no heartbeat for 30+ min")
```

Fixed (2026-06-18) — also checks for claim extensions that happened AFTER the last heartbeat:

```python
# ✅ New — skip if claim was extended after last heartbeat
last_claim_ext = (SELECT MAX(created_at) FROM task_events
                  WHERE kind = 'claim_extended' AND created_at > started_at)

if last_claim_ext > 0 and last_claim_ext > last_heartbeat_at:
    continue  # gateway confirmed PID alive → worker is just blocked on process wait
```

**Why `claim > hb` instead of a time threshold:** Claim extensions can be delayed
by dispatcher contention, DB locks, or system load — 45% of claim extension
intervals exceed 20 minutes. A time-based threshold inevitably misses cases.
But `claim > hb` is a boolean: the gateway checked the PID AFTER the worker's
last heartbeat. That's proof of life, regardless of timing.

**Verification (2026-06-18):** Across 11 auto-blocked tasks on knowledge-base,
10/11 would have been skipped with this rule. The 11th (t_71e292ee) was a
genuine crash-loop with zero heartbeats and zero claim extensions.

## Important: high CPU ≠ hung

Pyannote diarization at 441% CPU is **normal** multi-core processing. The
watchdog has no way to distinguish "working hard" from "genuinely stuck."
Only claim extension gaps signal dead workers. A subprocess consuming CPU
is doing work — do not kill it based on CPU metrics alone.

## Configuration

Override the default 15-min TTL:

```bash
export HERMES_KANBAN_CLAIM_TTL_SECONDS=3600  # 1 hour for very long tasks
```

Or per-task: `hermes kanban create ... --ttl 3600`
