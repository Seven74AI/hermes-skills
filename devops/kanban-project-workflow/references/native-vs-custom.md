# Hermes Kanban: Native vs Custom Infrastructure

Audit of what Hermes kanban provides natively vs what we built ourselves.
Based on the official docs (hermes-agent.nousresearch.com/docs) and source
code inspection. Last updated: 2026-05-22.

## Native Hermes Kanban

| Feature | How | Config |
|---------|-----|--------|
| Dispatcher | Picks up `ready` tasks, spawns workers | `dispatch_in_gateway: true`, `dispatch_interval_seconds: 60` |
| Worker lifecycle | Auto-injected via `KANBAN_GUIDANCE` + `kanban-worker` skill | — |
| `kanban_*` tools | show, complete, block, heartbeat, comment, create, link, unblock, list | — |
| Stale reclaim | 4h no heartbeat → auto-reclaim to `ready` | `dispatch_stale_timeout_seconds` (default 4h) |
| Failure auto-block | N consecutive spawn failures → auto-block | `failure_limit` (default 2) |
| Parent→child promotion | All parents `done` → child `todo→ready` | Built into dispatcher |
| Auto-decompose | LLM fans out `triage` tasks into child tasks | `auto_decompose: true` (default) |
| Task specification | `hermes kanban specify` → LLM fleshes out triage task | `auxiliary.triage_specifier` model |
| Workspace GC | `hermes kanban gc` — removes scratch workspaces for archived tasks | — |
| Idempotent create | `--idempotency-key` prevents duplicate tasks | — |
| Multi-board | Each board = separate SQLite DB | `hermes kanban boards create` |
| Tenant isolation | Soft namespace within a board | `--tenant` |
| Workspace types | `scratch`, `dir:<path>`, `worktree` | Task `workspace` column |

## Custom Infrastructure (Built by Us)

| Watchdog | What it does | Why custom | Cron |
|----------|-------------|------------|------|
| **CI watchdog** | Polls PRs with kanban labels, merges if CI green, unblocks task | Hermes has no PR merge automation. Workers push PRs but don't merge. | `10cb5de254d0`, every 2 min |
| **Block watchdog** | Detects reviewer deadlocks (reviewer blocked → unblock coder when fix done) | Hermes dispatcher promotes children when parents done, but doesn't unblock blocked siblings | Built into the `kanban-worker` skill / SOUL.md |
| **Pre-spawn watchdog** | Scans ready tasks for NO-SKILLS, NO-MRT, PR-URL-IN-BODY, PR-URL-COMMENTS | Validation of task creation quality — not a Hermes concern | `ceead0ca5089`, every 5 min |
| **Workspace GC cron** | Deletes workspaces of done/archived tasks | Redundant with native `hermes kanban gc`, but our cron auto-runs | `eb1ab33f9bf4`, every 15 min |
| **Skills sync cron** | Copies skills from main profile to all worker profiles | Hermes profiles have isolated `skills/` dirs | `4eee7fb0b484`, daily 3:30am |

## Future Simplification

### CI watchdog → light version
With `gh pr merge --auto --squash`, GitHub handles merges natively.
The CI watchdog shrinks to ~30 lines:

```python
# Only job: detect merged PRs → unblock kanban tasks
for pr in merged_prs_with_kanban_label:
    task_id = extract_task_from_label(pr["labels"])
    hermes kanban --board {board} unblock {task_id}
```

### Workspace GC → use native
`hermes kanban gc` exists. Consider removing the cron if native works.
Or repurpose the cron to call `hermes kanban gc` instead of custom script.

### Pre-spawn watchdog → keep notification-only
Catches task creation errors early. No automation — just alerts.
Could be replaced by better `hermes kanban create` validation.

### What NOT to touch
- **Block watchdog** — still needed for reviewer deadlocks (reviewer blocks after requesting changes → coder fixes → someone must unblock reviewer for re-review)
- **Skills sync** — needed as long as profiles have isolated skill dirs, unless we switch to auto-sync-on-spawn

## What We Never Used (but could)

- `hermes kanban specify` — LLM-driven task fleshing. Could replace manual task body writing.
- `kanban.auto_decompose: true` — auto-fan-out of triage tasks. Could replace planner role for simple cases.
- `--idempotency-key` — prevents duplicate tasks from cron/webhook automation.
