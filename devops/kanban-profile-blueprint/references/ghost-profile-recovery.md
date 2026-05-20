# Ghost Profile Recovery

## What this is

Tasks in `ready` or `running` state assigned to a profile that doesn't exist. The block watchdog
only scans `blocked` tasks — ghost-assigned `ready` tasks are invisible until `failure_limit` kicks
in. This recipe covers full recovery: create the profile, unstick the tasks, verify dispatch.

## Symptoms

```bash
hermes kanban --board <board> list | grep -E '(▶|●)'
# Shows tasks ready/running with assignee that's NOT in `hermes profile list`
```

## Recovery recipe (do in this order)

### 1. Create the missing profile(s)

```bash
# Clone from the closest existing profile
hermes profile create <project>-<role> --clone-from <base-profile>

# Fix nested model config (--clone may leave fields top-level)
python3 -c "
import yaml
path = '/root/.hermes/profiles/<project>-<role>/config.yaml'
with open(path) as f:
    cfg = yaml.safe_load(f)
cfg['model'] = {'default': 'deepseek-v4-pro', 'provider': 'deepseek', 'base_url': 'https://api.deepseek.com/v1'}
cfg.pop('provider', None)
with open(path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False)
"
```

### 2. Write SOUL.md

Copy from the closest template in `templates/` (coder, reviewer, researcher, planner, devops).
Adapt role-specific sections. MUST include:
- TOKEN ECONOMY with background+wait pattern
- `⚠️ NEVER use parent=task_id` warning
- `⛔ TERMINATE` section

### 3. Sync skills (CRITICAL — omission causes "Unknown skill" crashes)

```bash
rsync -a --delete /root/.hermes/skills/ /root/.hermes/profiles/<name>/skills/
```

### 4. Reclaim ghost tasks

```bash
# For each stuck task on the board:
for tid in <t_xxx> <t_yyy>; do
  hermes kanban --board <board> reclaim "$tid"
done
```

Note: `reclaim` works on `running` tasks (resets to `ready`). Tasks already in `ready` state
will be picked up automatically once the profile exists — the dispatcher rescans periodically.

### 5. Verify

```bash
hermes kanban --board <board> list | grep -E '(▶|●)'
# Should show tasks with the correct assignee, picked up by dispatcher
```

## Real case (2026-05-19, hermes-ops board)

- 6 tasks stuck: 5 `running` + 1 `ready`, all assigned to non-existent `hermes-devops`
- Created profile, wrote SOUL.md, synced 104 skills, reclaimed 6 tasks
- All 6 dispatched within seconds
- Also: `edgee-planner` and `twitter-coder` created in same pass for edgee-lab and twitter-digest boards
