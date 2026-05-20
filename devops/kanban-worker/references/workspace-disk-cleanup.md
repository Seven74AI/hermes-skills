# Workspace Disk Cleanup

Kanban `scratch` workspaces clone the full project repo including `node_modules/` (1.5–2.7 GB each). With `max_spawn=5` + accumulated done tasks, this can saturate a 72 GB disk in under a day.

## Diagnosis

```bash
# Check disk
df -h /

# Find workspace bloat per board
du -sh ~/.hermes/kanban/boards/*/workspaces/

# Find top workspace offenders
du -sh ~/.hermes/kanban/boards/music-library/workspaces/*/ | sort -rh | head -10
```

**Disk full symptoms**: kanban CLI fails with `disk I/O error`, gateway logging breaks with `OSError: [Errno 28] No space left on device`, workers crash.

## Automated GC

A cron job (`kanban workspace GC`, `eb1ab33f9bf4`) runs `~/.hermes/scripts/kanban-gc-workspaces.py` every 15 minutes. It deletes workspaces of done/archived tasks **older than 5 minutes** — enough to avoid race conditions with crash + re-dispatch, short enough to not accumulate.

If this job is missing:
```bash
hermes cron create \
  --name "kanban workspace GC" \
  --schedule "every 15m" \
  --script kanban-gc-workspaces.py \
  --no-agent \
  --deliver local
```

## Bulk manual cleanup (emergency)

When disk is already at 100% and kanban CLI fails, use Python directly against SQLite:

```python
import sqlite3, subprocess, os

base = '/root/.hermes/kanban/boards/music-library/workspaces'
db = os.path.join(os.path.dirname(base), 'kanban.db')
conn = sqlite3.connect(db)
rows = conn.execute(
    "SELECT id FROM tasks WHERE status IN ('done', 'archived') "
    "AND updated_at < datetime('now', '-1 hour')"
).fetchall()
conn.close()

for (tid,) in rows:
    ws = os.path.join(base, tid)
    if os.path.exists(ws):
        subprocess.run(['rm', '-rf', ws], timeout=5)

subprocess.run(['df', '-h', '/'])
```

**Safety rule**: always use `updated_at < datetime('now', '-1 hour')` in the query. Deleting a workspace immediately after a task crashes can corrupt the re-dispatch — the new worker finds an empty workspace and blocks with "Workspace corrupted."

## Non-workspace disk consumers

Also check these when diagnosing pressure:

```bash
du -sh /root/.cache/camoufox/          # Browser automation cache (~1.4G)
du -sh /root/.cache/ms-playwright/     # Playwright browsers (~640M)
du -sh /root/.npm/                     # npm package cache (~600M)
du -sh /root/.hermes/profiles/*/       # Profile venvs (3.5G for music-coder)
du -sh /tmp/playwright-artifacts-*     # Stale Playwright test artifacts
du -sh /tmp/playwright_chromiumdev_*   # Stale Chromium profiles
```

These are safe to delete — they rebuild on next use. The GC script only handles kanban workspaces; these require periodic manual cleanup or separate cron jobs.
