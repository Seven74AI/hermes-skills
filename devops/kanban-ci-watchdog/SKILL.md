---
name: kanban-ci-watchdog
description: CI-gated PR workflow for kanban boards — label-based PRs, CI-watchdog cron, respawn guard system, notification model, active_pr diagnosis and fix.
version: 1.0.1
metadata:
  hermes:
    tags: [kanban, ci, pr, watchdog, debugging]
---

# Kanban CI Watchdog

CI-gated PR merge workflow for autonomous kanban boards. Avoids `respawn_guarded`
by using GitHub labels instead of PR URLs in task comments.

## The Problem

The kanban dispatcher scans task comments for GitHub PR URLs. If ANY comment
within the last 24 hours contains a PR URL (`https://github.com/.../pull/N`),
the task is flagged `respawn_guarded` with reason `active_pr`. The worker
cannot spawn until 24h pass or the URL comment is deleted.

Source: `hermes_cli/kanban_db.py` line 4527 – `_RESPAWN_GUARD_PR_WINDOW = 86400`

## The Solution: Label-Based PRs

Workers use GitHub labels to link PRs to kanban tasks — NO PR URLs in comments.

### Worker Workflow

1. Implement feature, push branch to fork
2. Create PR on fork with kanban task label:
   ```bash
   gh pr create --repo Seven74AI/REPO --base main --head feat/N \
     --label "kanban:$HERMES_KANBAN_TASK"
   ```
3. **NEVER post the PR URL in a comment** — use the label reference only
4. Block: `kanban_block(reason="awaiting CI: PR label kanban:$HERMES_KANBAN_TASK")`
5. CI-watchdog finds PR via `gh pr list --label "kanban:"` → merges if green
6. Worker respawns → verifies merge → `kanban_complete`

If CI red → CI-watchdog comments error → unblocks → worker fixes → retry.

### Project Skill Update

Add this section to the project's skill:

```markdown
### ⛔ CRITICAL: Worker Git Workflow — Fork PRs only, label-based

**PRs on `Seven74AI/REPO` (fork): OK.** PRs on upstream: NEVER (consolidation only).

**Worker workflow (label-based — NO PR URLs in comments):**
1. Clone fork, implement, push branch, run local CI in background
2. Create PR on fork with label: `gh pr create --repo Seven74AI/REPO --base main --head feat/N --label "kanban:$HERMES_KANBAN_TASK"`
3. ⛔ NEVER post the PR URL in a comment. The dispatcher scans comments for GitHub PR URLs → `active_pr` → blocks respawn for 24h.
4. Block with: `kanban_block(reason="awaiting CI: PR label kanban:$HERMES_KANBAN_TASK")`
5. CI-watchdog finds PR via `gh pr list --label "kanban:"` → merges if CI green → unblocks coder
6. Coder respawns → verifies merge → kanban_complete

If CI red → CI-watchdog comments error → unblocks → coder fixes → repush → re-PR.

**Only consolidation merges to upstream.**
```

## Respawn Guard System

The dispatcher calls `check_respawn_guard()` on every `ready` task each tick (every 60s).
Three checks in strict priority order — the first match wins:

1. **`blocker_auth`** — `last_failure_error` matches a quota/rate-limit/auth pattern
   (429, 403, 401, 5xx, "rate limit", etc.). Defer a few ticks; the API may recover.
2. **`recent_success`** — a completed run exists within the last 1 hour.
   Prevents duplicate work; waits for human review of the prior run's output.
3. **`active_pr`** — any comment body in the last 24h matches
   `https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+`. Prevents duplicate PRs on
   the same task.

When the guard fires, the task is simply **skipped this tick** — it stays `ready`,
a `respawn_guarded` event is logged, and the dispatcher moves on. The guard is
**stateless** — re-evaluated fresh from current DB state every tick. When the
condition clears (comment deleted, 1h window expires), the task spawns normally.

API URLs (`api.github.com/repos/...`) and text references ("PR #95") do NOT
match the `active_pr` regex — only a raw `https://github.com/.../pull/N` URL.

## CI Watchdog Notification Model

The watchdog only outputs stdout when it **takes action**. The cron delivers
stdout to Discord + Telegram. Silent means nothing to do.

| State | Output | Notification |
|---|---|---|
| No "awaiting CI" tasks | silent | No |
| CI still running | silent | No |
| CI green → merge success | `merged PR #N` | Yes |
| CI green → merge failed | `merge FAILED PR #N` | Yes |
| CI red | `CI FAILED PR #N` | Yes |

**Merge-failed despite CI green** happens when: another PR merged to `main`
between CI completion and the watchdog's tick (conflict), branch protection
blocks merge, or the PR was closed externally. The watchdog unblocks the task
with `[CI-WATCHDOG] Merge failed — possible conflict.` so the worker can rebase.

## CI-Watchdog Cron Setup

The watchdog is a Python script running as a `--no-agent` cron job (no LLM needed).

### Script Template

See `scripts/ci-watchdog-template.py` for the full script. Copy and fill in BOARD + REPO.

Key logic:
1. `gh pr list --jq` client-side filter for kanban: labels (NOT `--label`, see pitfalls)
2. `gh run list --branch <branch>` → check CI status
3. If CI green → `gh pr merge --merge --delete-branch` → unblock task
4. If CI red → comment error → unblock task
5. Delete PR URL comments after merge to prevent `active_pr`

### Pitfalls (do NOT ship a watchdog with these bugs)

1. **`gh pr list --label kanban:` returns empty.** `--label` does EXACT match, not prefix. A label `kanban:t_abc123` does NOT match `--label kanban:`. Use `--jq` with `startswith("kanban:")` instead: `'--jq', '[.[] | select(.labels[].name | startswith("kanban:")) | ...]'`

2. **`WHERE t.status = 'blocked'` misses tasks.** The Kanban Block Watchdog can promote blocked tasks to `ready`, or workers can re-claim them to `running`. The CI watchdog must find tasks by BLOCK EVENT REASON, not current status. Query: `WHERE t.status NOT IN ('archived', 'completed', 'cancelled', 'done') AND te.kind = 'blocked' AND te.payload LIKE '%awaiting CI%'`

3. **`gh run view --repo X --log-failed` prints help text.** `gh run view` requires a run ID or URL as a positional argument (not just `--repo`). Pass `ci_url` from the `check_ci()` output: `gh run view <ci_url> --repo X --log-failed`

4. **SyntaxWarning `invalid escape sequence '\\('`.** Python string `"\\(.status)"` treats `\(` as an invalid escape. Use a raw string: `r'.[0] | "\(.status)|\(.conclusion)|\(.url)"'`

### Deploy

```bash
# Save script
cp ci-watchdog-<board>.py ~/.hermes/scripts/

# Create cron (every 2 min, no agent, local delivery)
hermes cron create \
  --name "<board> CI watchdog" \
  --schedule "every 2m" \
  --script ci-watchdog-<board>.py \
  --no-agent \
  --deliver local
```

## Diagnosis: Stuck Tasks (respawn_guarded)

### Symptoms
- Task stays `ready` but never spawns
- `hermes kanban show <id>` shows recent `respawn_guarded` events
- Reason: `active_pr`

### Diagnosis

```bash
# 1. Check for respawn_guarded events
python3 -c "
import sqlite3, json
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
events = conn.execute(\"SELECT task_id, payload FROM task_events WHERE kind='respawn_guarded' ORDER BY id DESC LIMIT 10\").fetchall()
for e in events:
    p = json.loads(e[1] or '{}')
    print(f'{e[0][:14]} | reason={p.get(\"reason\")}')
conn.close()
"

# 2. Find PR URL comments (the root cause)
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
rows = conn.execute(\"SELECT id, task_id, substr(body,1,80) FROM task_comments WHERE body LIKE '%github.com%pull%'\").fetchall()
for r in rows:
    print(f'  c{r[0]} | {r[1][:14]} | {r[2]}')
conn.close()
"

# 3. Delete PR URL comments to unblock immediately
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
conn.execute(\"DELETE FROM task_comments WHERE body LIKE '%github.com%pull%'\")
conn.commit()
print(f'Deleted {conn.total_changes} comments')
conn.close()
"

# 4. Also check block reasons for PR URLs
python3 -c "
import sqlite3, json
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
blocks = conn.execute(\"SELECT task_id, payload FROM task_events WHERE kind='blocked' ORDER BY id DESC LIMIT 20\").fetchall()
for b in blocks:
    p = json.loads(b[1] or '{}')
    reason = p.get('reason','')
    if 'github.com' in reason:
        print(f'{b[0][:14]} | {reason[:100]}')
conn.close()
"
```

### Fix

1. Delete PR URL comments (see above)
2. Close/merge any stale PRs on the fork
3. Ensure workers use label-based workflow going forward
4. Deploy CI-watchdog cron to prevent recurrence

## Velocity & Lifetime Tracking

Historical registry of completions and task lifetimes across all boards.

### Scripts

| Script | Purpose |
|--------|---------|
| `kanban-velocity.py` | Live snapshot — completions/lifetime for 4h/12h/24h/3j/7j/30j |
| `kanban-velocity-record.py` | Incremental recorder — stores daily snapshots in `~/.hermes/kanban/velocity-registry.json` |
| `kanban-velocity-view.py` | View history — `kanban-velocity-view.py [board]` for board-specific trend |

### Cron Setup

```bash
# Daily velocity recording at 3am
hermes cron create \
  --name "kanban velocity registry" \
  --schedule "0 3 * * *" \
  --script kanban-velocity-record.py \
  --no-agent \
  --deliver local
```

### Registry Format

`~/.hermes/kanban/velocity-registry.json` stores one snapshot per day:
```json
{
  "snapshots": [{
    "ts": 1779300000,
    "date": "2026-05-20 03:00",
    "totals": {"done": 774, "total": 1017, "running": 9, "avg_lifetime_s": 5393},
    "boards": {
      "shop": {"done": 180, "total": 237, "new_completions": 178, "avg_lifetime_s": 8400}
    }
  }],
  "last_processed": {"shop": 3950, "the-swarm": 1200}
}
```

`last_processed` tracks the highest event_id per board — only new completions since the last run are counted.

- **PRs on the fork count too.** The dispatcher scans comments for ANY GitHub PR URL — fork or upstream. A PR on `Seven74AI/REPO` triggers the same `active_pr` as a PR on `mnlamart/REPO`.
- **24-hour window.** Even after deleting the PR or the comment, if another comment with a PR URL exists within 24h, the guard fires. Delete ALL PR URL comments.
- **The block reason can also contain URLs.** If a worker blocks with `reason="PR #32 on ..."` and includes a URL, fix the skill so workers use labels instead.
- **Non-label PRs still block.** An open PR without a `kanban:` label still has a PR URL in comments. The CI-watchdog only finds labeled PRs. Unlabeled PRs need manual intervention.

## Pitfall: `WHERE t.status = 'blocked'` misses promoted tasks

**The CI watchdog must NOT filter on `t.status = 'blocked'`.** The Kanban Block Watchdog (or the worker itself) can promote/unblock a task while CI is still running. The task status changes to `ready` or `running` but the block event with `"awaiting CI"` still exists. Filtering by status makes the CI watchdog blind to these tasks.

**Wrong:**
```sql
WHERE t.status = 'blocked' AND te.kind = 'blocked' AND te.payload LIKE '%awaiting CI%'
```

**Correct:**
```sql
WHERE te.kind = 'blocked' AND te.payload LIKE '%awaiting CI%'
  AND t.status NOT IN ('archived', 'completed', 'cancelled', 'done')
```

Exclude terminal tasks but include `ready`, `running`, and `blocked` — any task that has an awaiting-CI block event needs the CI watchdog's attention, regardless of what happened to its status since.

### Symptoms of this bug

- Open kanban-labeled PR with CI running/completed but watchdog never acts on it
- Task has `blocked` event with "awaiting CI" but current status is `ready` or `running`
- Task keeps getting re-spawned while CI is still red
- Event timeline shows: `blocked → promoted → claimed → running` — watchdog missed it

## Block Watchdog Interaction

The Kanban Block Watchdog (`check-blocked-tasks.py`) does NOT auto-unblock "awaiting CI" tasks — it treats them as "unknown block type" (reports only, no action). This is correct behavior. The CI watchdog is the sole handler for CI-gated tasks.

However, if a task is manually unblocked or unblocked by the worker itself, the status changes and the CI watchdog (if using the buggy `t.status = 'blocked'` filter) loses track. The fix above addresses this on the CI watchdog side.

Add an `is_ci_blocked()` branch to `check-blocked-tasks.py` so "awaiting CI" blocks are categorized distinctly from "unknown block type" in Discord alerts:

```python
def is_ci_blocked(events):
    for evt in events:
        if evt.get("kind") == "blocked":
            if "awaiting CI" in evt.get("payload", {}).get("reason", ""):
                return True
    return False
```

## Diagnostic: Stuck Worker — Alive PID, Zero Heartbeat

A worker process can be alive (PID exists, claim auto-extended via `pid_alive`) but produce zero heartbeats. The process is stuck — typically blocked on an LLM call that never returns, or in a loop without checkpoint calls.

**Key indicators:**
- `status = 'running'`
- `consecutive_failures = 0` (never crashed, so circuit breaker won't trip)
- `last_heartbeat_at = NULL` (never sent a heartbeat)
- `claim_extended` events with `reason: pid_alive` in event history
- Process exists (`ps -p <pid>`) but state is `S` (sleeping)

**Why the circuit breaker doesn't help:**
`consecutive_failures` is incremented only on crash/timeout/failure. It resets to 0 on successful completion. A worker that never crashes and never completes keeps `consecutive_failures = 0` forever. The circuit breaker trips at `failure_limit` (default 3) — with 0 consecutive failures it never triggers.

**What eventually reclaims it:**
`dispatch_stale_timeout_seconds` (default 14400 = 4 hours). If no heartbeat is seen within that window, the dispatcher reclaims the task as stale. This is the ONLY mechanism that catches a zero-heartbeat-alive-PID worker.

**Diagnosis:**
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
conn.row_factory = sqlite3.Row
t = conn.execute('SELECT status, consecutive_failures, last_heartbeat_at, worker_pid FROM tasks WHERE id=?', ('<tid>',)).fetchone()
if t:
    print(f'status={t[\"status\"]}  cf={t[\"consecutive_failures\"]}  pid={t[\"worker_pid\"]}  hb={t[\"last_heartbeat_at\"]}')
conn.close()
"
# If pid is set, check if it's alive:
ps -p <pid> -o pid,state,etime,cmd --no-headers
```

## Queue Saturation: Guard-Cleared Tasks Not Spawning

When `max_spawn` is saturated (all worker slots full) or higher-priority tasks consume the dispatch budget, lower-priority tasks may not be re-evaluated for many ticks — even after their `respawn_guarded` guard has cleared.

**Symptoms:**
- Task is `ready`, `claim_lock = NULL`, `check_respawn_guard()` returns `None`
- But no new `spawned` or `respawn_guarded` events for 10+ minutes
- Other tasks ARE being spawned in the same time window
- The task is at the bottom of the priority queue, behind unassigned or higher-priority tasks

**This is not a bug.** It's normal queue behavior. The task will spawn when the dispatcher reaches it. Check with:
```bash
# See how many ready tasks are ahead in the queue
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
conn.row_factory = sqlite3.Row
ready = conn.execute('SELECT id, title, priority, assignee FROM tasks WHERE status=\"ready\" ORDER BY priority DESC, created_at ASC').fetchall()
for i, t in enumerate(ready):
    marker = ' <--' if t['id'] == '<tid>' else ''
    print(f'{i+1}. prio={t[\"priority\"]} {t[\"id\"][:16]} assignee={t[\"assignee\"]} {marker}')
conn.close()
"
```
