# Kanban Autoscale — Configuration & Pitfalls

The `kanban-autoscale.py` script (~/.hermes/scripts/) runs every 5 minutes as a `no_agent` cron job. It clones profiles when ready tasks exceed capacity and deletes idle clones.

## Script location

`~/.hermes/scripts/kanban-autoscale.py`

Cron job: `kanban-autoscale` (job `f853c2212844`), schedule `every 5m`, `no_agent: true`.

## Key Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| `MAX_PROFILES_PER_ROLE` | **2** | Avoid OOM — 7.8Gi RAM + 10Gi swap. Each profile spawns one hermes process per task; 8 clones × 5 tasks = 40+ concurrent processes = lock contention + OOM. |
| `SCALE_UP_THRESHOLD` | 2 | Clone when ready tasks > profiles × 2 |
| `MIN_IDLE_MINUTES` | 10 | Must be idle this long before scale-down deletes |

## How it works

- **Scale-up**: counts ready tasks per role across all boards. If ready > profiles × threshold, clones the base profile (e.g., `coder-2`). Starts clone numbering at 2.
- **Scale-down**: checks if a clone has zero tasks assigned AND has been idle for `MIN_IDLE_MINUTES`. Uses `hermes profile delete <name> --yes` (non-interactive).
- **State file**: `~/.hermes/scripts/.autoscale_state.json` tracks `last_active` timestamps per profile.

## Critical Pitfalls (fixed)

### 1. MAX=8 caused massive overspawn

**Symptom**: `hermes profile list` hangs, `ps aux | grep hermes | wc -l` shows 60+ processes. System becomes unresponsive due to SQLite lock contention.

**Root cause**: With MAX=8 and many ready tasks across boards, the autoscale created 8 clones per role. The dispatcher spawned one hermes process per task per clone — exponential blowup.

**Fix**: Cap at 2. Each role gets base profile + max 1 clone = at most 2 concurrent workers per role.

### 2. Scale-down was broken (missing `--yes`)

**Symptom**: Idle clones accumulated, never deleted.

**Root cause**: Script used `echo '{p}' | hermes profile delete {p}` — piping the profile name into stdin. The `--yes` flag is the correct non-interactive form. Pipe `echo y` does NOT work either.

**Fix**: `hermes profile delete {p} --yes`

### 3. MIN_IDLE_MINUTES defined but never enforced

**Symptom**: Clone could be deleted immediately after completing a task, before the dispatcher assigns the next one — race condition.

**Root cause**: The constant was defined but the scale-down logic checked only `profile_task_count == 0`, not how long the profile had been idle.

**Fix**: State file tracks `last_active` per profile. Scale-down checks `idle_seconds >= MIN_IDLE_MINUTES * 60`.

## Diagnosing Overspawn

```bash
# Count kanban workers
ps aux | grep 'hermes.*kanban.*work kanban task' | grep -v grep | wc -l

# Group by profile
ps aux | grep 'hermes.*kanban.*work kanban task' | grep -v grep | \
  awk '{for(i=1;i<=NF;i++) if($i ~ /^-p$/) print $(i+1)}' | sort | uniq -c | sort -rn

# Check system load
free -h
uptime
```

## Recovery Steps

1. Kill excess workers: `pkill -f 'hermes.*kanban.*work kanban task'`
2. Delete excess clone profiles: `hermes profile delete <name> --yes`
3. Verify script has MAX=2: `grep MAX_PROFILES ~/.hermes/scripts/kanban-autoscale.py`
4. Wait for dispatcher to re-claim tasks (stale claims are auto-reclaimed)

## Profile Delete Quirk

`hermes profile delete <name> --yes` is the ONLY reliable non-interactive form. Both `echo y | hermes profile delete <name>` and `echo '<name>' | hermes profile delete <name>` fail — the command prompts interactively and ignores piped stdin.

## Tuning max_spawn Without Autoscale

When autoscale is paused, `max_spawn` (in `~/.hermes/config.yaml` under the kanban section) is the sole concurrency control. Each worker process consumes ~180 MB RSS. Safe upper bound:

```
max_spawn ≤ (total_RAM_GB - 3) / 0.2
```

The 3 GB buffer covers: gateway (~300 MB), TypeScript tsserver (up to 2.2 GB when active on a project), OS overhead, and swap headroom.

**Tested values on 7.8 GB RAM:**
| max_spawn | RAM used | Risk |
|-----------|----------|------|
| 2 | ~50% | Safe |
| 5 | ~32% | Safe (verified 24h) |
| 8 | ~57% | Moderate |

Going beyond 8 without autoscale should be paired with swap monitoring (`free -h`, `swapon --show`) and gateway cgroup checks (`systemctl show hermes-gateway | grep MemorySwap`).

**Important**: the `max_spawn` limit is per-board, not global. If multiple boards are active, total workers = sum of per-board limits. Keep this in mind when tuning.
