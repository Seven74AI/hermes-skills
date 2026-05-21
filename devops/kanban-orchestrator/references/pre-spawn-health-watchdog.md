# Pre-Spawn Health Watchdog

## Problem

Kanban tasks in `ready` status can have hidden issues that prevent dispatch or cause immediate failure:
- **Missing assignee** → dispatcher ignores the task, it sits in `ready` forever
- **Missing skills** → worker spawns without skill guidance, crashes on first complex operation
- **Missing max_runtime_seconds** → fallback to 120s, causing timeout loops on real work
- **PR URLs in body or comments** → dispatcher's `respawn_guarded` blocks respawn for 24h

These issues are invisible until the dispatcher tries to claim the task — and by then, worker slots and CPU cycles are already wasted.

## Solution

A no-agent cron watchdog (`~/.hermes/scripts/pre-spawn-watchdog.py`) that scans ALL boards every 5 minutes, flags `ready` tasks with issues, and reports them. **Notification only — never modifies tasks.**

```bash
hermes cron create \
  --name "Pre-Spawn Health Watchdog" \
  --schedule "every 5m" \
  --script pre-spawn-watchdog.py \
  --no-agent \
  --deliver discord:<channel>,telegram:<chat_id>
```

## Checks performed

| Check | Condition | Severity |
|-------|-----------|----------|
| NO-ASSIGNEE | `ready`/`blocked` task with no `assignee` | Blocks dispatch completely |
| NO-SKILLS | `ready`/`running` task with no `skills` (non-reviewer) | Worker spawns without guidance |
| NO-MRT | `ready`/`running` task with no `max_runtime_seconds` (non-reviewer) | Falls back to 120s → timeout loops |
| PR-URL-BODY | PR URL in task `body` via regex `pull/\d+` | `respawn_guarded` for 24h |
| PR-URL-COMMENTS(N) | PR URL in comments via same regex | `respawn_guarded` for 24h |

## Exclusions (intentional skips)

| Pattern | Why excluded |
|---------|-------------|
| `title LIKE 'RECETTE:%'` | Merge-target tasks — never dispatched, no assignee by design |
| `assignee = 'reviewer'` | Reviewer tasks — dispatcher injects profile skills, 120s fallback is sufficient |
| `title LIKE 'Review:%'` | Also reviewer tasks — same reason |

## False-positive sources (lessons from 2026-05-20)

### 1. Broad SQL LIKE matches action-run URLs

The dispatcher's `_RESPAWN_GUARD_PR_URL_RE` regex is `github\.com/[^/\s]+/[^/\s]+/pull/\d+` — it matches PR URLs specifically. But CI watchdog comments contain action-run URLs with `?exclude_pull_requests=true` in the query string. A SQL `LIKE '%github.com%pull%'` matches the query parameter and flags false positives.

**Fix:** Use the same regex as the dispatcher (`pull/\d+`), not broad SQL LIKE.

```python
# ❌ Broad — matches action URLs with ?exclude_pull_requests
conn.execute("SELECT COUNT(*) FROM task_comments WHERE task_id=? AND body LIKE '%github.com%pull%'", (tid,))

# ✅ Precise — same regex as dispatcher
_PR_URL_RE = re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+", re.IGNORECASE)
count = sum(1 for (body,) in comments if body and _PR_URL_RE.search(body))
```

**Real case:** shop/t_4b967237 had 7 CI-WATCHDOG comments with action URLs. The SQL `LIKE '%github.com%pull%'` matched `exclude_pull_requests` in the query string → 7 false positives.

### 2. RECETTE merge targets

RECETTE tasks (Phase 0-5 merge targets) are intentionally unassigned — they're organizational, never dispatched. Without the RECETTE exclusion, 6 tasks were flagged every 5 minutes.

### 3. Reviewer tasks flagged for NO-SKILLS/NO-MRT

Reviewer tasks created by the block watchdog often have `skills=NULL` and `max_runtime_seconds=NULL`. The dispatcher injects profile skills, and the 120s fallback is sufficient for review tasks. Flagging them is noise.

## Silent pattern

Like all no-agent watchdogs, the script MUST be silent when clean:

```python
if not issues:
    return  # stdout empty → no cron notification delivered
```

The header (`🔍 PRE-SPAWN HEALTH — HH:MM`) only prints when issues are found.
