# Kanban Velocity Tracking

Completions per period + ticket lifetime tracking across all boards.

## Quick Use

**Live dashboard** (completions + lifetime for last 4h/12h/24h/3d/7d/30d):
```bash
python3 ~/.hermes/scripts/kanban-velocity.py
```

**View history** (from registry, incremental daily snapshots):
```bash
python3 ~/.hermes/scripts/kanban-velocity-view.py           # all boards
python3 ~/.hermes/scripts/kanban-velocity-view.py shop      # single board
```

**Daily health monitor** (velocity + system + blocked tasks, Discord-friendly):
```bash
python3 ~/.hermes/scripts/kanban-daily-monitor.py
```

**Fallback when scripts aren't installed at `~/.hermes/scripts/`:** run them from the skill directory:
```bash
SKILL_DIR=~/.hermes/skills/devops/kanban-project-workflow
python3 $SKILL_DIR/scripts/kanban-velocity/kanban-velocity.py
python3 $SKILL_DIR/scripts/kanban-velocity/kanban-velocity-view.py
```
If `kanban-daily-monitor.py` is missing, combine `kanban-velocity.py` (live dashboard) + manual `df -h /`, `free -h`, and `uptime` for the same system-health snapshot.

## Scripts

Located in `scripts/kanban-velocity/`:
- `kanban-velocity.py` — query-based live dashboard (reads task_events directly)
- `kanban-velocity-record.py` — incremental recorder for cron (stores in JSON registry)
- `kanban-velocity-view.py` — history viewer (reads JSON registry)
- `kanban-velocity-backfill.py` — one-shot utility: hydrate existing snapshots with token data from state.db

## Registry

Stored at `~/.hermes/kanban/velocity-registry.json`. Each run of `kanban-velocity-record.py`:
- Processes only completions since its last recorded event_id per board
- Appends a snapshot with per-board done/total/running/new_completions/avg_lifetime
- Keeps last 90 days

## Cron Setup

```bash
hermes cron create \
  --name "kanban velocity registry" \
  --schedule "0 3 * * *" \
  --script kanban-velocity-record.py \
  --no-agent \
  --deliver local
```

## Metrics Tracked

| Metric | Description |
|--------|-------------|
| Completions | Tasks completed per period |
| Rate | Completions per hour |
| Lifetime (avg) | Mean time from creation to completion |
| Lifetime (median) | 50th percentile — half finish faster |
| Fastest/Slowest | Outlier detection |
| Tokens (avg) | Mean tokens spent per ticket (input+output from session state.db) |
| Tokens (total) | Total tokens across all completions in the snapshot |
| Per-board breakdown | Each board's progress + velocity |

## Daily Health Monitor

Lightweight ops script combining velocity + system health + blocked task count. Designed for `no_agent=true` cron delivery to Discord.

```bash
python3 ~/.hermes/scripts/kanban-daily-monitor.py
```

**Helper: count blocked tasks across all boards:**
```bash
python3 ~/.hermes/scripts/count-blocked-tasks.py
```

## Pitfalls

- **Corrupted/empty kanban.db:** if `kanban.db` has 0 tables (e.g. after a disk-full event or filesystem error), `count-blocked-tasks.py` and the live dashboard may hang or timeout. The velocity registry (`velocity-registry.json`) is independent and usually survives — use `kanban-velocity-view.py` for historical data and check board state files directly for blocked-task counts.
- The registry is JSON-based and loaded entirely into memory. For 90 days of daily snapshots across 10+ boards, this is ~100KB — negligible.
- If the cron job misses a day, the next run will batch all missed completions into one snapshot (not backfill daily buckets).
- The live dashboard (`kanban-velocity.py`) queries task_events directly and can be slow on large boards with millions of events. The registry approach is more efficient for historical queries.
- Token data comes from `state.db` in each profile directory. If a session's state.db has been cleaned/pruned, token data will be unavailable for that ticket (shown as N/A).
- Token counts are input_tokens + output_tokens from the session that created the task (stored as `session_id` on the task).
