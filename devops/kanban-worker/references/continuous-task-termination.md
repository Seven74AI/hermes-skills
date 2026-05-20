# Continuous Task Termination — ⛔ Pattern

## Problem

Workers on continuous monitoring tasks run their sweep, complete their work,
send a heartbeat... then **exit the process without calling `kanban_block()`**.
The kanban dispatcher sees this as:

```
worker exited cleanly (rc=0) without calling kanban_complete or kanban_block
— protocol violation
```

The worker's session log is clean — work was done, comments posted, nothing
crashed. But the task is marked as `crashed` and the `consecutive_failures`
counter increments. After 3-5 failures, the dispatcher `gave_up` and the
task stops being dispatched even when unblocked.

**Root cause:** The worker's SOUL.md says "post findings as comments" but
never explicitly instructs the worker to call a terminal function
(`kanban_block` or `kanban_complete`) before the process exits. The worker
finishes its work and the Python process ends naturally — but without the
protocol-required terminal call.

## Real-world example (edgee-lab T-WATCH, 2026-05-18)

Run #79 (edgee-watcher):
- Started at 18:25
- Completed full sweep: 4 HIGH + 3 MEDIUM signals found
- Posted findings as kanban comments
- Sent heartbeat at 18:31: "Watch round complete..."
- Process exited at 18:32 (~6 min runtime)
- **No `kanban_block()` or `kanban_complete()` called**
- Result: crash #5, `gave_up`, circuit breaker triggered

Run #80 (after SOUL.md fix — same profile, same task):
- Started at 18:58
- Completed sweep: 8 findings (3 HIGH, 4 MEDIUM, 1 LOW)
- Called `kanban_block(reason="Sweep #1 complete. 8 findings posted...")` at end
- Result: clean block, task ready for next cycle ✅

## The fix — SOUL.md ⛔ TERMINATE section

Replace vague instructions with an ABSOLUTE REQUIREMENT section that the
worker cannot miss. Use dramatic formatting (⛔, MUST, "CRASH") to make it
visually distinct from other SOUL.md content.

### Template (add to end of watcher SOUL.md)

```
- ⛔ TERMINATE (ABSOLUTE REQUIREMENT — if you forget this you CRASH and the task is bricked):
  After every sweep, regardless of findings, call ONE of:
  A) `kanban_block(reason="Sweep #N complete. X findings posted. Ready for next cycle.")` — for normal monitored runs
  B) `kanban_complete(summary="Sweep complete. X findings posted.")` — for cron one-shots
  YOU MUST DO THIS. Not optional. Not "maybe next time." Every single run ends with this call.
  Crashing = wasted tokens, bricked task, human escalations. Do not exit without it.
  If you've been running for >5 minutes or >30 tool calls: STOP what you're doing and call kanban_block immediately. Partial findings + clean exit > full sweep + crash.
```

## Why this works

1. **Visual salience** — ⛔ emoji catches attention in a wall of text
2. **Absolute language** — "ABSOLUTE REQUIREMENT", "YOU MUST", "Not optional"
3. **Consequence stated** — "CRASH", "bricked task", "wasted tokens"
4. **Deadline** — ">5 minutes or >30 tool calls: STOP and block NOW"
5. **Both options given** — worker knows exactly which function to call

## Why generic instructions fail

The original edgee-watcher SOUL.md said:
> "When you find something relevant, post it as a Kanban comment"

The worker did exactly that — posted comments, then exited. It followed the
letter of the instruction. The missing piece was the terminal function call,
which was never mentioned.

Workers follow SOUL.md instructions literally. If it says "post as comment"
and doesn't mention `kanban_block()`, the worker will post comments and exit.

## When to use this pattern

- Continuous monitoring tasks (watchers, daemons, periodic sweeps)
- Any task where the worker runs autonomously and must survive multiple cycles
- Tasks dispatched by cron that expect the worker to report and wait for the
  next cycle

## When NOT to use this pattern

- One-shot tasks that should `kanban_complete()` when done
- Short-lived tasks (<2 minutes) — just `kanban_complete()`
- Tasks where the worker should heartbeat and stay alive for hours

## Related: circuit breaker reset

If a task has already hit the circuit breaker (`consecutive_failures >= failure_limit`),
unblock alone won't work. Reset in SQLite first:

```python
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
db.execute("UPDATE tasks SET consecutive_failures = 0 WHERE id = '<task_id>'")
db.commit()
db.close()
```

Then `hermes kanban unblock <task_id>` and dispatch.
