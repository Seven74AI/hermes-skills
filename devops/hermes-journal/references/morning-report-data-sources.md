# Morning Report — Non-Kanban Data Sources

Quick-reference for the daily Morning Report cron job (`82a083aaa98e`).
Docs the schemas and safe query patterns for sources that aren't kanban (see `kanban-db-queries.md` for those).

## `jobs.json` — Cron Job Inventory

**Path:** `/root/.hermes/cron/jobs.json`

**Structure:**
```json
{
  "jobs": [
    {
      "id": "8628d151e230",
      "schedule": {"kind": "cron", "expr": "0 4 * * *", "display": "0 4 * * *"},
      "description": "...",
      "prompt": "..."
    }
  ],
  "updated_at": "2026-06-10T06:02:23+02:00"
}
```

**Key pitfall:** This is a **dict** wrapping a `jobs` list, not a flat list. Direct iteration over the loaded JSON will fail.

**Safe query (no pipe-to-interpreter):**
```bash
python3 -c "
import json
with open('/root/.hermes/cron/jobs.json') as f:
    data = json.load(f)
jobs = data.get('jobs', data)  # tolerate both shapes
if isinstance(jobs, list):
    for j in jobs:
        jid = j.get('id','?')
        sched = j.get('schedule',{})
        desc = j.get('description', j.get('prompt','?'))[:100]
        display = sched.get('display', sched.get('expr','?'))
        print(f'{jid[:14]} | {display:20s} | {desc}')
"
```

Schedule shapes:
- `{"kind": "cron", "expr": "0 6 * * *", "display": "0 6 * * *"}`
- `{"kind": "interval", "minutes": 10, "display": "every 10m"}`

## Session Search Patterns

Use `session_search()` — the FTS5-backed function, not raw file reads.

**Morning Report queries:**
1. **Browse recent** (no args): `session_search()` — returns last 10 sessions chronologically
2. **Find interactive (non-cron)** sessions: `session_search(query="NOT cron", sort="newest", limit=5)`
3. **Find error/incident sessions**: `session_search(query="error OR crash OR fail OR OOM OR gateway", sort="newest", limit=5)`
4. **Check for user decisions**: `session_search(query="interactive OR décision OR décidé", sort="newest", limit=5)`

**Key pitfall:** Most sessions in a 24h window will be cron-sourced. The `source` field distinguishes `"cron"` from interactive sources (CLI, Discord, etc.).

## GitHub Activity

**Repos to check** (loop ~/.hermes/ projects + code repos):
```bash
cd /root && for d in */; do
  if [ -d "$d/.git" ]; then
    cd "$d"
    git log --since="24 hours ago" --all --oneline --no-merges 2>/dev/null
    cd ..
  fi
done
```

Plus the hermes-agent install:
```bash
cd /usr/local/lib/hermes-agent && git log --since="24 hours ago" --all --oneline --no-merges
```

And the backup repo (always churns with backup+prune cycles):
```bash
cd /root/.hermes/backups && git log --since="24 hours ago" --oneline
```

**Key pitfall:** The backup repo will always have commits (backup + prune every 2h). Filter these mentally — they're infrastructure, not code changes.

## Error Log Triage

**Path:** `/root/.hermes/logs/errors.log`

**Morning Report patterns to check:**
```bash
# Count recurring warnings
grep -c "Binding to 0.0.0.0" /root/.hermes/logs/errors.log

# API failures
grep -c "Broken pipe\|Stream stale" /root/.hermes/logs/errors.log

# Security scanner blocks
grep -c "pending_approval" /root/.hermes/logs/errors.log
```

**Key pitfall:** The dashboard pinger generates a "Binding to 0.0.0.0 --insecure" warning every 5 minutes (288/day). These are noise, not alerts. Report them once, note the volume, don't flag each occurrence.
