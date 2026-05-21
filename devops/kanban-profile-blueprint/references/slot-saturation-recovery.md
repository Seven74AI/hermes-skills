# Slot Saturation Recovery

When `max_spawn` limits are reached and all worker slots are occupied
by stuck/zombie tasks, the board freezes — ready tasks queue forever
with 0 blocked tasks.

## Symptoms

- Board shows 0 blocked but 20+ ready tasks waiting 7-12h
- All running tasks have high run counts (>10) or stale heartbeats (>30 min)
- Progress % unchanged for hours
- `max_spawn` config at its limit (e.g. 5)

## Recovery recipe

```bash
# 1. Diagnose each running task
python3 << 'PYEOF'
import sqlite3, time, os
now = time.time()
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
db.row_factory = sqlite3.Row
for t in db.execute("""
    SELECT t.*, (SELECT COUNT(*) FROM task_runs WHERE task_id = t.id) AS runs
    FROM tasks t WHERE status='running'
"""):
    r = dict(t)
    hb = int((now - (r['last_heartbeat_at'] or 0)) / 60) if r['last_heartbeat_at'] else 999
    pid = r['worker_pid']
    alive = False
    if pid:
        try: os.kill(pid, 0); alive = True
        except OSError: pass
    # Check last comment for review-required
    last_comment = db.execute(
        "SELECT body FROM task_comments WHERE task_id=? ORDER BY id DESC LIMIT 1",
        (r['id'],)
    ).fetchone()
    is_done = last_comment and 'review-required' in (last_comment[0] or '')
    
    issues = []
    if is_done: issues.append("DONE (review-required posted)")
    if not alive: issues.append("PID DEAD")
    if hb > 120: issues.append(f"ZOMBIE ({hb}m no hb)")
    if r['runs'] >= 15: issues.append(f"LOOP ({r['runs']} runs)")
    
    if issues:
        print(f"{r['id']}: {' | '.join(issues)}")
db.close()
PYEOF

# 2a. Mark done tasks as done (SQL) + create standalone review
python3 -c "
import sqlite3, time
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
db.execute(\"UPDATE tasks SET status='done', completed_at=? WHERE id='t_xxx'\", (int(time.time()),))
db.commit()
db.close()
"
hermes kanban --board <board> create "Review: (t_xxx) <summary>" --assignee reviewer --max-runtime 300s

# 2b. Kill zombie workers + reclaim
python3 -c "
import sqlite3, os, signal
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
row = db.execute('SELECT worker_pid FROM tasks WHERE id=\"t_xxx\"').fetchone()
if row and row[0]:
    try: os.kill(row[0], signal.SIGKILL)
    except: pass
db.close()
"
hermes kanban --board <board> reclaim t_xxx

# 2c. Bump runtime for timeout-loop tasks
python3 -c "
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
db.execute('UPDATE tasks SET max_runtime_seconds = 1200 WHERE id = \"t_xxx\"')
db.commit()
db.close()
"
hermes kanban --board <board> reclaim t_xxx

# 3. NEVER use 'hermes kanban block' to free a slot
#    The dispatcher auto-unblocks when parents are done.
#    If you need to stop a task: mark it done (SQL) or archive it.
```

## Why blocking doesn't work

`promote_ready()` in kanban_db.py auto-promotes blocked tasks to `ready`
when all their parent tasks are `done`. The block is immediately
reversed on the next dispatcher tick — the task goes right back to
running.

## Prevention

- Set `--max-runtime` on every task at creation (600s default)
- Don't let review-required tasks stay `running` — mark them `done`
- Monitor heartbeats; reclaim any task with no heartbeat > 1h
