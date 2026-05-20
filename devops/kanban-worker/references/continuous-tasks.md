# Continuous Kanban Tasks

Tasks that run in cycles (monitor → report → block → unblock → repeat) rather than one-shot completion.

## Pattern

```
Sweep → post findings as comments → kanban_block() → unblocked by human/watchdog → next sweep
```

The task NEVER calls `kanban_complete()` — it blocks itself between cycles. The human or watchdog unblocks it to trigger the next cycle.

## SOUL.md Requirements

The worker profile's SOUL.md **MUST** make the termination instruction unmissable. Workers will default to "I'm done → I'll just exit" unless explicitly forced otherwise.

### Required section

```markdown
- ⛔ TERMINATE (ABSOLUTE REQUIREMENT — if you forget this you CRASH):
  After every sweep, regardless of findings, call ONE of:
  A) `kanban_block(reason="Sweep #N complete. X findings posted.")` — monitored runs
  B) `kanban_complete(summary="Sweep complete. X findings posted.")` — cron one-shots
  Do not exit without it.
  If >5 minutes or >30 tool calls: STOP and call kanban_block immediately.
```

Key design points:
- Use `⛔` or `⚠️` to make it visually distinct
- State the consequence: "if you forget this you CRASH"
- Include a time/tool-count escape hatch so the worker stops early rather than crashing
- Make it the FIRST instruction, not buried at the bottom

## Common Failure Modes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| "protocol violation: worker exited without kanban_block" | SOUL.md missing termination instruction | Add the ⛔ TERMINATE section |
| Worker crashes with budget exhaustion | `max_turns` too low for the sweep | Increase to 180-360 in profile config |
| "pid not alive" after clean session | Worker finished sweep, exited without calling terminal function | Strengthen SOUL.md termination language |
| `consecutive_failures` triggers circuit breaker | 3+ crashes without recovery | Reset in SQLite: `UPDATE tasks SET consecutive_failures = 0 WHERE id = '<id>'` |

## Circuit Breaker Reset

When a task reaches `consecutive_failures >= failure_limit`, the dispatcher gives up. Reassigning with `--reclaim` or unblocking won't help — the counter must be reset directly:

```bash
python3 -c "
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
db.execute(\"UPDATE tasks SET consecutive_failures = 0 WHERE id = '<task_id>'\")
db.commit()
db.close()
"
```

After reset, unblock and dispatch normally.

## Example: Edgee Lab T-WATCH

A technology watch task that scans 6+ sources (blogs, Reddit, HN, GitHub, Twitter/X) and posts findings as comments. Each sweep takes 5-15 minutes. The worker blocks between cycles so the human can review findings before the next sweep.

Profile config:
- `max_turns: 360` (5-15 minute sweeps need headroom)
- SOUL.md: ⛔ TERMINATE section at the top
- Workspace: persistent so findings accumulate across cycles
