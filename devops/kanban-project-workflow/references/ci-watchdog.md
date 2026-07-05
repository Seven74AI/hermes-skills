# Kanban CI Watchdog (Simplified — Unblock Only)

The CI watchdog no longer merges PRs. GitHub native auto-merge (`gh pr merge --auto`)
handles merging when CI is green and the reviewer approves.

The watchdog's ONLY job: poll for merged PRs with kanban labels → unblock the task.

## Why Simplified

Previously the watchdog: (1) checked CI status, (2) merged PRs, (3) unblocked tasks.
GitHub auto-merge now handles steps 1-2. The watchdog does step 3 only.

## The Problem (Still Applies)

The kanban dispatcher scans task comments for GitHub PR URLs. If ANY comment
within the last 24 hours contains a PR URL, the task is flagged `respawn_guarded`
with reason `active_pr`. Workers must use labels, not PR URLs.

## Unified PR Workflow

See `kanban-project-workflow` for the full flow. Summary:

1. Coder creates PR with label `kanban:t_xxx`, enables auto-merge
2. Coder creates reviewer task, blocks with `review-required`
3. Reviewer approves → GitHub auto-merges when CI green
4. **This watchdog detects the merge → unblocks the coder**
5. Coder respawns → verifies → completes

## Respawn Guard System (Still Active)

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
| No merged PRs with kanban label | silent | No |
| PR merged → unblocked | `merged + unblocked t_xxx` | Yes |
| PR merged but task not found | `orphan PR #N (label kanban:t_xxx) — task not found` | Yes |

## Light Watchdog Script

Deployed at `~/.hermes/scripts/ci-watchdog-light.py`. Handles all active boards:

```python
"""Light CI Watchdog — unblocks kanban tasks when their PRs are merged."""
import subprocess, re, sqlite3, json

BOARDS = {
    "shop": "Seven74AI/shop",
    "the-swarm": "Seven74AI/the-swarm",
    # Add new boards here
}

for board, repo in BOARDS.items():
    result = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--state", "merged",
         "--limit", "20", "--json", "labels,number",
         "--search", "label:kanban:"],
        capture_output=True, text=True
    )
    if not result.stdout.strip():
        continue
    prs = json.loads(result.stdout)

    for pr in prs:
        for label in pr["labels"]:
            m = re.match(r"kanban:(t_[a-f0-9]+)", label["name"])
            if not m:
                continue
            task_id = m.group(1)

            # Only unblock if the task currently exists and is blocked
            db = sqlite3.connect(f"/root/.hermes/kanban/boards/{board}/kanban.db")
            cur = db.execute(
                "SELECT status FROM tasks WHERE id=? AND status='blocked'",
                (task_id,)
            )
            if cur.fetchone():
                subprocess.run(
                    ["hermes", "kanban", "--board", board, "unblock", task_id],
                    capture_output=True
                )
                print(f"Unblocked {task_id} on {board} (PR #{pr['number']} merged)")
            db.close()
```

Key differences from the old watchdog:
- No `gh pr merge` call — GitHub auto-merge handles it
- No CI status checks — branch protection enforces CI before merge
- Multi-board with SQLite validation (only unblocks blocked tasks)
- Silent when no work done (cron `--deliver local` with `--no-agent`)

### Why `--label` doesn't work for prefix matching

`gh pr list --label kanban:` does EXACT match, not prefix. A label `kanban:t_abc123`
does NOT match `--label kanban:`. Use `--json` + `re.match("kanban:", ...)` instead.

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

## Pitfalls

- **PRs on the fork count too.** The dispatcher scans comments for ANY GitHub PR URL — fork or upstream. A PR on `Seven74AI/REPO` triggers the same `active_pr` as a PR on `mnlamart/REPO`.
- **24-hour window.** Even after deleting the PR or the comment, if another comment with a PR URL exists within 24h, the guard fires. Delete ALL PR URL comments.
- **The block reason can also contain URLs.** If a worker blocks with `reason="PR #32 on ..."` and includes a URL, fix the skill so workers use labels instead.
- **Non-label PRs still block.** An open PR without a `kanban:` label still has a PR URL in comments. The CI-watchdog only finds labeled PRs. Unlabeled PRs need manual intervention.
- **`gh pr list --label` does exact match.** `gh pr list --label kanban:` does EXACT label name match, not prefix. A label `kanban:t_abc123` does NOT match `--label kanban:`. Use `--json labels` + regex in Python instead.
- **Non-label PRs still trigger active_pr.**
