# Budget Exhaustion Without Handoff — t_8e211ca6 Incident

**Date:** 2026-07-13  
**Board:** music-library  
**Task:** t_8e211ca6 — Fix 10/16 player-queue E2E tests  
**Profile:** coder (max_turns=180)

## Pattern

Worker repeatedly hits iteration budget without saving a handoff. Watchdog auto-unblocks
("iteration budget" matches TECHNICAL FAILURE rule), next worker starts from zero, same
budget hit repeats. Zero progress across 4 runs.

## Run Timeline

| Run | Outcome | Duration | Error |
|-----|---------|----------|-------|
| 1095 | blocked (review-required) | 50 min | PR #160, 7/16 pass |
| 1097 | crashed | 38 min | pid not alive (OOM suspect) |
| 1098 | **blocked** | 43 min | **Iteration budget exhausted (180/180)** |
| 1104 | crashed | 61 min | protocol violation (worker exited cleanly without complete/block) |

Zero handoff.md files created across all runs.

## Root Cause

Worker ignores budget checkpoints and runs until exhaustion. No Memento Pattern
trigger at 66% of budget (~119 turns for 180-turn profile).

## Why the Memento Pattern Failed

1. **Hardcoded turn numbers**: The original skill said "60 turns = 66%" — correct
   for 90-turn profiles, wrong for 180-turn profiles (60 = 33%).
2. **Worker ignores checkpoints entirely**: Even with correct numbers, the worker
   doesn't voluntarily stop and save progress. It keeps working until the gateway
   kills it.

## Fix Applied

1. **Dynamic checkpoints**: Budget checkpoints now compute from `max_turns`:
   - `checkpoint_33 = floor(budget × 0.33)` → heartbeat
   - `checkpoint_66 = floor(budget × 0.66)` → Memento Pattern trigger
   - `checkpoint_83 = floor(budget × 0.83)` → danger zone
2. **Pre-flight handoff check**: When a worker starts after a budget-exhaustion
   block, it checks for `handoff.md` in the workspace before starting fresh work.
3. **Explicit calculation formula**: The skill now shows the formula for workers
   to compute their own checkpoints.

## Remaining Risk

The Memento Pattern is documented in the skill but workers may still ignore it.
The checkpoint is voluntary — no hard enforcement in the agent loop. A worker that
dives into inline test runs will exhaust its budget regardless of the skill text.

Mitigation: the pre-flight check at least prevents the NEXT worker from starting
from zero if a handoff was saved.

## Successful Run #1110 (with updated skill)

After the skill was patched with dynamic checkpoints and synced to the coder
profile, run #1110 completed in 36 minutes with a clean `review-required` block:

- **16/16 tests passing**, PR #166 created
- Reviewer task `t_09d8355c` created correctly
- **No budget exhaustion, no crash**
- Worker appeared to follow the correct pattern (review-required block after
  creating reviewer task)

## Stale claim_lock from Gateway (Secondary Finding)

After killing the deadlocked run #1109, the task was reset to `ready` but the
dispatcher refused to spawn for 20+ consecutive ticks. Gateway logs showed:

```
kanban dispatcher stuck: ready queue non-empty for 21 consecutive ticks but 0 workers spawned
```

The root cause: `claim_lock` was set to `vmi3304846:3817737` — the gateway's own
PID. The block watchdog cron (running inside the gateway process) had auto-unblocked
the task but left the claim_lock intact. The dispatcher skips tasks with non-NULL
claim_lock regardless of status.

**Fix:** `UPDATE tasks SET claim_lock=NULL WHERE id='<id>';` — no gateway restart
needed. Task spawned on the next dispatcher tick (~60s).
