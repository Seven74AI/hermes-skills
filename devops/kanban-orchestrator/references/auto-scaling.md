# Autonomous Profile Scaling — Hybrid Architecture

## Rationale

Manual profile scaling (Step 2.5) works for orchestration sessions but leaves idle
clones lying around between sessions. The goal: profiles scale themselves — no
dedicated orchestrator profile or human intervention needed.

## Implementation: Unified Python Cron Script

A single Python script (`scripts/kanban-autoscale.py`) handles both scale-up
and scale-down. It runs via a `no_agent=true` cron every 2 minutes. Zero tokens,
zero LLM — pure counting logic.

### Scale-Up Logic

```
For each Kanban board:
  For each role (derived from assignee profile names):
    ready_count = tasks with status "ready"
    profile_count = existing profiles matching this role
    
    threshold = profile_count * 2
    if ready_count > 0 and needed > profile_count and profile_count < 2:
      clone new profile: hermes profile create <role>-<N> --clone-from <role>
```

**Threshold: ready > profiles × 2.** Creates buffer before bottleneck. At 2
profiles with 5 ready tasks → clone to 3. Conservative enough to avoid thrashing.

**Cap: 2 profiles per role.** Hard limit to prevent OOM on memory-constrained hosts. Each profile spawns a full gateway + model process, so beyond 2 per project you hit OOM on typical setups.

### Scale-Down Logic

```
For each profile:
  if profile is a clone (name matches <base>-<N> where N >= 2):
    if this specific profile has 0 tasks assigned:
      if other profiles exist for this role (> 1 total):
        delete: hermes profile delete <name> --yes
```

**Only deletes clones, never base profiles.** The base profile (e.g.,
`music-coder` without suffix) is the template and stays forever.

**Per-profile check, not per-role.** A clone is only deleted when it has zero
tasks of its own — not when the whole role is idle. This avoids deleting a
clone that's between tasks.

## Why Not Per-Worker Cleanup?

The initial design proposed decentralized scale-down: each clone profile
schedules its own deletion after completing its last task. This was abandoned
because:

1. **Workers lack the `cronjob` tool.** They can't schedule their own deletion.
2. **A profile can't delete itself while running.** Requires a delayed cron.
3. **The 2-minute cron is simpler and sufficient.** It catches idle clones
   quickly without adding complexity to the worker lifecycle.

The unified approach is preferred: one script, one cron, both directions.

## Comparison: Shell vs Python

| | Shell (`auto-scale-up.sh`) | Python (`kanban-autoscale.py`) |
|---|---|---|
| Scale-up | Yes | Yes |
| Scale-down | No | Yes |
| Parsing | Fragile text grep on `hermes kanban list` | Robust JSON via `--json` flag |
| Multi-board | Via text parsing | Via `--json` + env var |
| Profile detection | Regex on table output | Deduplicated name extraction |
| Cron | every 5 min | every 2 min |

**Use the Python script.** It handles both directions and uses JSON parsing.

## CLI Quirks (Discovered During Implementation)

- `hermes profile list --json` does NOT work — must parse table output.
  Filter out separator lines (`────`) and header row.
- `hermes kanban list --json` works and returns full task objects with
  `status`, `assignee`, `tenant` fields.
- `hermes kanban boards list --json` works, returns board slugs + counts.
- `HERMES_KANBAN_BOARD=<slug>` env var switches board context for
  `hermes kanban list`.
- Cron schedule `"2m"` = one-shot, `"every 2m"` = recurring forever.
- Profile deletion requires confirmation: pipe name to stdin or use `--yes`.

## Deployment

```bash
# One-time setup
hermes cron create "every 2m" \
  --name kanban-autoscale \
  --no-agent \
  --script kanban-autoscale.py
```

The cron runs forever, 0 tokens per tick. Manual cleanup of idle clones
(Step 2.5) becomes optional — the system self-regulates.

## Limitations

- **Scale-up only helps independent tasks.** Serial pipelines won't benefit
  from more profiles.
- **Same-file conflicts.** Two coders editing the same file = merge conflicts.
  Use the split-and-merge pattern for those cases.
- **Does not handle cross-project role merging.** `shop-coder` and
  `music-coder` are treated as separate roles. To share profiles, rename
  them to a common prefix (e.g., `coder`, `coder-2`).
