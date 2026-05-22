# Hermes Kanban: Native vs Custom Infrastructure

Audit of what Hermes kanban provides out of the box vs what was custom-built.
Use this when debugging kanban issues — check native features first, then customs.

## Native Hermes (built-in)

| Feature | Config/Details |
|---------|---------------|
| Embedded dispatcher | `dispatch_in_gateway: true`, tick every 60s |
| Worker lifecycle | `KANBAN_GUIDANCE` auto-injected into system prompt |
| `kanban_*` tools | show, complete, block, heartbeat, comment, create, link, unblock, list |
| Stale task reclaim | `dispatch_stale_timeout_seconds` (4h default, 1h no heartbeat) |
| Auto-block after failures | `failure_limit` (default 2) consecutive spawn failures |
| Parent→child promotion | All parents done → child `todo→ready` auto |
| Auto-decompose | `auto_decompose: true` — fans out triage tasks via LLM |
| Triage→spec | `hermes kanban specify` — LLM fleshes out triage tasks |
| Workspace GC | `hermes kanban gc` — removes scratch workspaces |
| Multi-board | `hermes kanban boards` — isolated SQLite DB per board |
| Tenant isolation | `--tenant` — soft namespace within a board |
| Idempotent create | `--idempotency-key` — dedup retried automation |
| Bulk operations | `hermes kanban complete t1 t2 t3` |
| `kanban-orchestrator` skill | Bundled skill for orchestrator patterns |

## Custom (built by us)

| Feature | What it does | Why custom |
|---------|-------------|-----------|
| CI watchdog | Merges PRs when CI green (OLD) / detects merged PRs (LIGHT) | Hermes has no auto-merge |
| Block watchdog | Handles review deadlocks (reviewer blocked → promote coder) | Hermes has no review gate logic |
| Pre-spawn watchdog | Validates tasks before spawn (missing skills, PR URLs) | Safety net for config errors |
| kanban-project-workflow | Documents the unified PR workflow, fork/direct models, pitfalls | Our conventions |
| kanban-profile-blueprint | Team setup recipe (profiles, SOUL.md, tenant) | Our conventions |
| Workspace GC cron | `kanban-gc-workspaces.py` | Redundant with `hermes kanban gc` native |
| Profile skill sync | Copies skills to worker profiles | Needed because profiles have isolated `skills/` dirs |

## Things we DON'T need (but thought we did)

- **Separate CI-gated vs review-gated models**: Unified into one flow (reviewer + auto-merge)
- **Custom merge logic in CI watchdog**: GitHub auto-merge (`gh pr merge --auto`) handles it
- **Workspace GC cron**: Use `hermes kanban gc` native instead

## Key config flags

```yaml
kanban:
  dispatch_in_gateway: true     # default
  dispatch_interval_seconds: 60 # default
  failure_limit: 2              # default
  max_spawn: 5                  # set on resource-constrained hosts
  auto_decompose: true          # default — auto fans out triage tasks
```
