# max_spawn Overspawn Bug — Evidence & Code Walkthrough

**Date:** 2026-05-20
**Board:** shop
**Config:** `kanban.max_spawn: 5`
**Gateway restart:** 02:46:52 (config loaded: `max_spawn=5`)
**Observation:** 7 workers running on shop board despite cap of 5

## Timeline

| Task | Started (UTC) | Delta |
|---|---|---|
| t_16f50502 | 08:26:29 | — |
| t_fc27e601 | 08:28:55 | +2:26 |
| t_558b1b1a | 08:28:55 | same second |
| t_d4fcf739 | 08:28:55 | same second |
| t_9bdf2106 | 08:28:56 | +1s |
| t_a9da4425 | 08:28:56 | +1s |
| t_909ed0ee | 08:28:57 | +2s |

6 tasks spawned in 2 seconds from the same dispatcher tick (interval=60s).
Running count at tick start should have been 1 (t_16f50502), allowing at most 4 more (1+4=5).

## Dispatcher Code (kanban_db.py:dispatch_once)

```python
# Step 6 — running_count computed ONCE per tick
running_count = 0
if max_spawn is not None:
    running_count = int(conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'running'"
    ).fetchone()[0])

# Spawn loop — checks running_count + spawned but never re-queries
spawned = 0
for row in ready_rows:
    if max_spawn is not None and running_count + spawned >= max_spawn:
        break       # ← caps at max_spawn, but only counts spawns in THIS loop
    # ... skip checks ...
    claimed = claim_task(...)   # sets status='running'
    pid = _spawn(...)           # spawns worker process
    spawned += 1
```

## Root Cause Hypothesis

The `running_count` is computed once at tick start (line 4694). If tasks were
promoted `todo → ready` by `recompute_ready()` at line 4683 and then spawned
immediately, the count is accurate. But if `release_stale_claims()` at line 4669
released t_16f50502's claim before the count, `running_count` could have been 0
instead of 1 — allowing 5 spawns. The 6th spawn would still be unexplained without
a deeper investigation of the claim TTL and stale-release timing.

Alternatively, the dispatcher may have ticked twice in rapid succession
(unlikely with 60s interval but possible during gateway startup or if a manual
`hermes kanban dispatch` was run concurrently).

## Per-Board Semantics

`max_spawn` is **per-board, not global**. With 10 boards and `max_spawn=5`:
- Theoretical max: 50 concurrent workers
- Each board independently caps at 5
- No cross-board enforcement exists

```python
# gateway/run.py — one tick per board, same max_spawn for all
def _tick_once():
    for slug in list_boards():          # iterates ALL boards
        _tick_once_for_board(slug)      # passes max_spawn=5 to each
```

## Diagnostic Commands

```bash
# Count running workers per board
for db in ~/.hermes/kanban/boards/*/kanban.db; do
  board=$(basename $(dirname "$db"))
  count=$(sqlite3 "$db" "SELECT COUNT(*) FROM tasks WHERE status='running';")
  echo "$board: $count"
done

# Count actual worker processes
ps aux | grep 'kanban-worker.*work kanban task' | grep -v grep | wc -l

# Check gateway log for max_spawn value
grep 'max_spawn' ~/.hermes/logs/gateway.log | tail -3

# Verify worker start times
ps -eo pid,lstart,args | grep 'kanban-worker' | grep -v grep
```

## Mitigation

1. Set `max_spawn` to `cores - 1` or lower (e.g. 2-3 for 4-core VMs)
2. Remember it's per-board — with 10 boards, set `max_spawn=2` for 20 max workers
3. After any config change: `hermes gateway restart` + reclaim all running tasks
4. Monitor with: `ps aux | grep 'kanban-worker' | wc -l` periodically
