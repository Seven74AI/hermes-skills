# Block Watchdog Pattern

## Problem

Kanban workers occasionally block tasks abnormally:
- Worker crashes (OOM, process killed)
- Iteration budget exhausted
- Timeout
- Systemic resource exhaustion (too many concurrent workers)

Without a watchdog, these tasks stay blocked forever, requiring manual operator intervention.

## Solution

A cron-based watchdog that runs every 5 minutes:

1. **Script** (`~/.hermes/scripts/check-blocked-tasks.py`) — scans all boards for blocked tasks, outputs structured context
2. **Cron job** (`hermes cronjob create`) — LLM-driven agent that investigates each blocked task and decides:
   - **TECHNICAL FAILURE** → unblock + comment
   - **REVIEW-REQUIRED** → create reviewer task if missing, then block
   - **LEGITIMATE** → leave alone

## Setup

```bash
# 1. Deploy both scanner scripts
#    check-blocked-tasks.py  — scans --status blocked
#    check-crash-loops.py    — scans running + consecutive_failures >= 5
#    watchdog-all.py         — wrapper that runs both

# 2. Create the cron job
hermes cronjob create \
  --name "Kanban Block Watchdog" \
  --schedule "every 5m" \
  --script watchdog-all.py \
  --enabled-toolsets terminal \
  --prompt "... watchdog prompt ..."
```

## Watchdog Agent Prompt (canonical)

The agent prompt should cover these cases:

1. **PIPELINE LIMIT** — worker reached pipeline cap ("2-video limit", "budget checkpoint", "handoff created") → `unblock` + comment. Cooldown: only if blocked > 3 min.
2. **TECHNICAL FAILURE** — crash, OOM, iteration budget, timeout → `unblock` + comment
3. **REVIEW-REQUIRED (coder)** — coder finished, blocking for review → check if a DISPATCHABLE reviewer task exists; if not, `kanban create` one WITHOUT `--parent`
4. **REVIEWER BLOCKED** — reviewer created follow-up, follow-up is now done → `unblock` the reviewer
5. **LEGITIMATE** — human-in-the-loop, explicit phase gate, "cookies expired" → do nothing

### Dispatchability check (CRITICAL — must verify before skipping)

When checking whether a reviewer task exists for a REVIEW-REQUIRED block, do NOT stop at "task found." Verify the task can actually be picked up:

```
For each task on this board assigned to 'reviewer' whose title references the blocked task ID:
  → If task status is 'done' or 'archived' — that reviewer already ran. Create a NEW one (re-review needed).
  → If task status is 'todo' — check its parents. If ANY parent is 'blocked', the task is DEADLOCKED.
    Archive the deadlocked task and create a new reviewer WITHOUT `--parent`.
  → If task status is 'ready' or 'running' — reviewer is already being handled. Do nothing.
```

**Why this matters:** A reviewer created with `--parent <blocked_task_id>` appears in `todo` but the dispatcher never promotes children of blocked parents. The watchdog sees "reviewer exists" and moves on — while the reviewer rots in `todo` forever. Real case: startup-lab 2026-05-18 — 4 reviewer tasks created (3 by watchdog itself, 1 by coder), all deadlocked by `parent=t_430b4de7` (blocked). The watchdog ran for 6+ hours without detecting the deadlock.

## Key Lesson: review-required without reviewer task

The most common pathology: a coder blocks with `review-required` but never creates a reviewer task (or creates one with `--parent`, deadlocking it). The watchdog must detect both cases and create a dispatchable replacement. The kanban-worker skill (v2.1.0+) now mandates creating the reviewer task BEFORE blocking — WITHOUT `--parent` — to prevent this pathology at the source.

### When the watchdog creates a reviewer task

**NEVER use `--parent`.** Reviewer tasks MUST be standalone so they dispatch immediately. Include the blocked task ID in the title (`Review: (t_xxx) ...`) and body text so the reviewer knows what to review. The reviewer will unblock the coder when done — that's how the pipeline flows, not through parent links.

**Check for duplicates first.** Scan existing tasks for ones with similar titles referencing the same blocked task ID. If a dispatchable reviewer already exists, don't create a duplicate. If only deadlocked duplicates exist, archive them then create the real one.

## Crash-Loop Watchdog (`check-crash-loops.py`)

The block watchdog only sees tasks with `status='blocked'`. A task in a **crash loop** stays `status='running'` because the dispatcher keeps respawning it — the watchdog never sees it. Same for **timeout loops** where the worker exceeds `max_runtime_seconds` every run but `consecutive_failures` stays 0 (kanban bug — timeout doesn't increment the counter).

### Detection phases

**Phase 1 — Crash loops:** `consecutive_failures >= CRASH_LOOP_THRESHOLD` (default 5). Catches genuine crashes (segfault, OOM, protocol violation). Standard, unchanged.

**Phase 2a — Timeout loops (run count):** tasks with `total_runs >= 20` AND current run has been going `>30 min`. Catches tasks that timeout→respawn endlessly but don't trigger `consecutive_failures`. The `>30 min` filter prevents false positives on freshly-reclaimed tasks that have historical runs but are now running fine with corrected settings.

**Phase 2b — Stale tasks:** tasks running `>1h` with no heartbeat in `>30 min`. Catches workers that died silently (no exit, no crash signal).

### DB sync

When a timeout loop is detected (20+ runs), the watchdog patches `consecutive_failures` in the DB directly: `UPDATE tasks SET consecutive_failures = MIN(total_runs, 99) WHERE consecutive_failures < CRASH_LOOP_THRESHOLD`. This fixes the kanban bug where timeout doesn't increment the counter, so Phase 1 detection works next cycle.

### Query optimization

Uses a single `LEFT JOIN` with a pre-aggregated subquery (`GROUP BY task_id` on `task_runs`) instead of per-row correlated subqueries. This avoids O(n²) lookups on boards with 400+ task_runs. Previously the script would timeout (30s+) when scanning boards with heavy run histories; now completes in <5s.

## Known Limitations

- Delivery to messaging platforms (Telegram, Discord) can fail with `RuntimeError('cannot schedule new futures after interpreter shutdown')` — use `deliver: local` and have the watchdog comment directly on tasks instead.

- **`needs changes` blocks classified as `unknown` (fixed 2026-07-13):** `check-blocked-tasks.py` added `is_needs_changes_blocked()` — matches block reasons containing `"needs change"` case-insensitively. Before this fix, reviewer tasks blocked with `needs changes: ...` fell through to "unknown block type" in the watchdog output. The watchdog now reports them as `needs-changes-blocked (reviewer verdict, fix in progress)`.
- When too many workers run concurrently, OOM kills workers → tasks cycle crash→unblock→crash. Fix: set `kanban.max_spawn` (see skill body) to cap concurrent workers at 2-3. This is the definitive fix — cloning/removing profiles does not address the root cause (dispatcher spawns per-task, not per-profile).
- **Timeout loops with <20 runs aren't detected by Phase 2a** — the run-count threshold is 20 to avoid false positives from normal retry cycles. Tasks with 5-19 runs that are stuck in timeout are caught by Phase 2b if they run >1h without heartbeat.
- **`consecutive_failures` kanban bug.** Timeout runs don't increment `consecutive_failures` in the DB (the `enforce_max_runtime → _record_task_failure` code path looks correct but the counter stays 0 on observed tasks with 400+ timed_out runs). Phase 2 and the DB sync work around this. Root cause not yet identified in `kanban_db.py`. Fix at source when discovered.

## Delivery: ALWAYS `origin`

**The watchdog MUST deliver to `origin`**, not `local`. When set to `local`, the report is saved to a file nobody reads. A task can block with the same reason for 15+ runs (e.g., missing OAuth setup) without the user ever knowing. The watchdog is the user's alert system — silencing it defeats its purpose.

```bash
# Correct:
hermes cronjob create ... --deliver origin
# Wrong:
hermes cronjob create ... --deliver local
```

## Escalation Rules

The watchdog should escalate when the same issue repeats, rather than silently retrying forever:

| Condition | Action |
|-----------|--------|
| Same task blocked with **same reason** for **3+ watchdog runs** | 🔴 **ESCALATE** — add to top of report: "ESCALATION: `<task_id>` blocked N runs with `<reason>`. Human intervention needed." |
| Same task **unblocked 3+ times** still blocking with **same technical reason** | 🔴 **REPEATED BLOCKER** — do NOT unblock again. Escalate: "REPEATED BLOCKER: `<task_id>` blocked N times with `<reason>`. Needs root cause fix, not another unblock." |
| **Reviewer blocked with `needs changes` + active fix task exists** | ✅ **NOT STUCK** — do NOT flag either the reviewer or the original coder. The fix chain is active: reviewer found issues → fix coder is working. Only escalate if the fix chain is broken (fix task done but coder still blocked without re-review). |

### "Needs Changes" chain recognition (critical — avoids false stuck reports)

When a reviewer blocks with `needs changes` and creates a fix coder task, the chain is:

1. **Coder** blocks `review-required` → creates **reviewer** task
2. **Reviewer** reviews → finds issues → blocks `needs changes: <summary>` → creates **fix coder** task
3. **Fix coder** is running/ready

The watchdog must recognize this chain. When checking a `review-required` coder:

```python
# For each review-required coder:
#   1. Find the reviewer task that blocked with "needs changes"
#   2. Find the fix coder task the reviewer created
#   3. If fix coder is active (ready/running) → chain is healthy → do NOT flag
#   4. If fix coder is done/archived AND no new review cycle started → chain broken → escalate
```

**Quick SQL check:**
```sql
-- Given a review-required coder t_coder:
-- 1. Find the reviewer
SELECT t2.id, t2.status, t2.latest_summary 
FROM tasks t1
JOIN task_links l ON l.parent_id = t1.id
JOIN tasks t2 ON t2.id = l.child_id
WHERE t1.id = 't_coder' AND t2.assignee = 'reviewer';

-- 2. Find the fix task created by that reviewer
SELECT t3.id, t3.status, t3.assignee
FROM task_comments c
JOIN tasks t3 ON c.body LIKE '%' || t3.id || '%'
WHERE c.task_id = '<reviewer_id>' 
  AND c.author = 'reviewer'
  AND t3.status IN ('ready', 'running');
```

**Real case (2026-07-13, music-library):** t_3b1ff519 (coder, `review-required`), t_f6c9490d (reviewer, `needs changes`), t_8e211ca6 (fix coder, `running`). Watchdog reported both t_3b1ff519 and t_f6c9490d as blocked — but the fix chain was active. The watchdog should have recognized: reviewer verdict rendered → fix coder active → chain healthy → suppress.

These rules prevent silent failure loops where the watchdog unblocks a task, the dispatcher retries, it fails with the same error, and the cycle repeats indefinitely without the user knowing.

## Retry cooldown tuning

The cooldown between crash retries is configured in `check-blocked-tasks.py` via `BACKOFF_SCHEDULE`. The current schedule is **linear**: `[120, 240, 360, 480, 600]` (2, 4, 6, 8, 10 minutes — 30 minutes total before escalation).

### Trade-off: linear vs exponential

| Approach | Schedule | Total before escalation | Best for |
|----------|----------|------------------------|----------|
| **Linear** (current) | `[120, 240, 360, 480, 600]` | 30 min | Fast feedback, busy boards where a stuck task wastes a worker slot |
| **Exponential** (old default) | `[300, 600, 1200, 2400, 4800]` | 155 min | Fragile systems where crashes need real cool-down time (e.g. rate-limit recovery, resource contention) |

**Linear is preferred for kanban boards with `max_spawn` caps.** When worker slots are scarce (e.g. `max_spawn=5` with 25 ready tasks), a stuck task burning retries holds a slot that healthy tasks need. Fast failure → fast escalation → slot freed.

### When to switch back to exponential

If crashes are rate-limit related (API throttling, CI runner exhaustion) and retrying every 2 minutes makes the problem worse (hammering the rate limiter), exponential backoff gives the system breathing room. But kanban crashes are rarely rate-limit related — they're more often OOM, broken code, or missing config — so fast escalation is usually better.

### How to change

```bash
# Edit the schedule in the script
$EDITOR ~/.hermes/scripts/check-blocked-tasks.py
# Line: BACKOFF_SCHEDULE = [120, 240, 360, 480, 600]
# No cron prompt update needed — the values are purely in the script.
```

## Script (`check-blocked-tasks.py`)

Key implementation notes:
- Each `hermes kanban` call has a 30s timeout (not 10s — the original script would timeout when the system was under load, causing `last_status=error`)
- Exit code is always 0 when the script runs successfully (even when blocked tasks are found). A non-zero exit signals a genuine script error. The original script exited with `sys.exit(total)` which made the cron system report `last_status=error` on every run that found blocked tasks.
- Per-board error handling: if one board's `kanban list` fails, the script continues to the next board instead of aborting.
- The watchdog agent receives the script output as context and decides which blocked tasks to unblock — the script is a data collector, not the decision-maker.

## Pitfall: Cron prompt drift from reference doc

**Problem:** The canonical prompt lives in this reference doc. When it's updated (e.g. dispatchability check added), the live cron job's prompt is NOT auto-synced — it keeps running the old prompt. The watchdog silently degrades.

**Real case (2026-05-18):** `block-watchdog.md` had dispatchability rules, but cron job `7ad8ddd5b9c9` ran a stale prompt without them. Result: 4 reviewer tasks deadlocked by `parent=t_430b4de7` (blocked), watchdog saw "reviewer exists" for 6+ hours and did nothing.

**Fix:** After updating this reference doc, update the cron job's prompt immediately:

```bash
# Get the job ID
hermes cron list | grep -B1 "Kanban Block Watchdog"

# Update with cronjob tool — pass the full prompt from the canonical section above
hermes cronjob update <job_id> --prompt "<canonical prompt from this doc>"

# ⛔ REQUIRED: restart gateway for the updated prompt to take effect
# The cron scheduler caches prompts at startup. Without a restart, the watchdog
# keeps using the old prompt indefinitely — it will appear to run (last_status=ok)
# but classify tasks under obsolete rules.
hermes gateway restart
```

**Prevention:** Treat the reference doc, the cron job's prompt, AND the gateway restart as a single unit. When one changes, change the other two. Never update the reference and walk away.
