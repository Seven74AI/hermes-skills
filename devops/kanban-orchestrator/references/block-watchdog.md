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
# 1. Deploy the scan script (Python, scans all boards)
#    See ~/.hermes/scripts/check-blocked-tasks.py

# 2. Create the cron job
hermes cronjob create \
  --name "Kanban Block Watchdog" \
  --schedule "every 5m" \
  --script check-blocked-tasks.py \
  --enabled-toolsets terminal \
  --prompt "... watchdog prompt ..."
```

## Watchdog Agent Prompt (canonical)

The agent prompt should cover these cases:

1. **TECHNICAL FAILURE** — crash, OOM, iteration budget, timeout → `unblock` + comment
2. **REVIEW-REQUIRED (coder)** — coder finished, blocking for review → check if a DISPATCHABLE reviewer task exists; if not, `kanban create` one WITHOUT `--parent`
3. **REVIEWER BLOCKED** — reviewer created follow-up, follow-up is now done → `unblock` the reviewer
4. **LEGITIMATE** — human-in-the-loop, explicit phase gate → do nothing

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

## Known Limitations

- Delivery to messaging platforms (Telegram, Discord) can fail with `RuntimeError('cannot schedule new futures after interpreter shutdown')` — use `deliver: local` and have the watchdog comment directly on tasks instead.
- When too many workers run concurrently, OOM kills workers → tasks cycle crash→unblock→crash. Fix: set `kanban.max_spawn` (see skill body) to cap concurrent workers at 2-3. This is the definitive fix — cloning/removing profiles does not address the root cause (dispatcher spawns per-task, not per-profile).

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

These rules prevent silent failure loops where the watchdog unblocks a task, the dispatcher retries, it fails with the same error, and the cycle repeats indefinitely without the user knowing.

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
```

**Prevention:** Treat the reference doc and the cron job's prompt as a single unit. When one changes, change the other. Never update the reference and walk away.
