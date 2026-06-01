# Assessing Whether Blocked Workspaces Are Cleanable

When automated cleanup steps (2g, 2h, 2ha) produce 0 results but disk usage is still high, blocked/running workspaces are often the culprit. Before archiving them, verify they're truly stale — not just momentarily blocked.

## Heuristic: disk mtime check

Blocked tasks don't report heartbeats reliably (some do, some have NULL). The kanban agent's workspace directory `mtime` is a better signal — it reflects actual filesystem activity (git operations, file writes, etc.).

```python
import os, time
ws = '/root/.hermes/kanban/boards/<board>/workspaces'
now = int(time.time())
for d in sorted(os.listdir(ws)):
    dp = os.path.join(ws, d)
    mtime = os.path.getmtime(dp)
    age_h = (now - mtime) / 3600
    size = sum(os.path.getsize(os.path.join(r,f)) for r,_,files in os.walk(dp) for f in files)
    print(f'{d}: {size/1024**2:.0f}M mtime={time.ctime(mtime)[:19]} age={age_h:.1f}h')
```

## Decision thresholds

| mtime age | Action |
|-----------|--------|
| < 2h | Likely active — leave alone |
| 2–6h | Gray zone — check heartbeat too |
| > 6h | Stale — safe to archive |
| None (0M dir) | Empty — delete directly (no DB change needed) |

## Example from 2026-05-31

5 music-library workspaces at 9.9G total, all blocked/running:
- 4 of 5 had mtime < 1h → left alone (active workers)
- No false positives despite all being `blocked`
