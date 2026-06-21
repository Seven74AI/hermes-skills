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

## Kanban Data — Quick Schema Reference

For detailed query patterns, **LOAD** `references/kanban-db-queries.md` (has safe python3 -c templates for every common query).

**CRITICAL gotchas (these will waste 3-4 calls if you guess):**

- **Timestamps are Unix integers**, NOT SQL datetime strings. `created_at`, `started_at`, `completed_at` are all `INTEGER` seconds since epoch. To compare with "24 hours ago", use `time.time() - 86400` in Python, not `datetime('now','-24 hours')` in SQL.
- **No `updated_at` column** on the `tasks` table. Use `completed_at` for completion tracking, `started_at` for work-in-progress.
- **Per-board DBs** live at `/root/.hermes/kanban/boards/<slug>/kanban.db`. The central `/root/.hermes/kanban.db` has a different schema (`workspace_kind` column).
- **`tasks.status` values differ**: central DB has `done`/`blocked`/`archived`; per-board DBs add `running`/`ready`/`todo`.
- Table is `tasks` (NOT `tickets`), events table is `task_events` with column `kind` (NOT `event_type`).
- Always use `python3 -c "import sqlite3..."` — bare `sqlite3` binary may not be present in cron environments.

## Session Search Patterns

Use `session_search()` — the FTS5-backed function, not raw file reads.

**CRITICAL: FTS5 searches message *content*, not session metadata.** The `query` parameter matches words inside messages — it cannot filter by `source`, `model`, or other session-level fields. A query like `"NOT cron"` excludes sessions where the word "cron" appears in messages, which is *accidentally* useful (cron system prompts contain "cron") but not semantically correct. A query like `"interactive"` matches any session whose messages contain that word, regardless of `source`.

**CRITICAL: Broad FTS5 queries return massive results (>500KB).** OR-heavy queries like `"error OR fix OR crash OR decision OR deploy OR create OR merge"` routinely match hundreds of messages across dozens of sessions, producing 500KB–1.2MB responses. These get **persisted to `/tmp/hermes-results/call_XX_<random>.txt`** with a preview (first 1500 chars) in the tool output. The agent gets a file path, not inline content. **Do NOT try to process these inline** — use `terminal` with `python3 -c` to grep or slice the persisted file (e.g., `python3 -c "print(open('/tmp/hermes-results/call_00_XXX.txt').read()[5000:8000])"`). Better yet, use **narrower queries** — targeted keywords like `"kanban block watchdog completed ticket"` produce manageable results (5-20 messages) while still finding relevant sessions. The broad queries are only useful for discovery when you don't know what you're looking for; once you have context, switch to targeted queries or scroll with `session_search(session_id=..., around_message_id=...)`.

**Morning Report queries (what actually works):**

1. **Browse recent** (no args): `session_search()` — returns 3 most recent sessions chronologically (NOT 10)

2. **Find non-cron sessions — SQL fallback (most reliable):**
   ```bash
   python3 -c "
   import sqlite3, time
   conn = sqlite3.connect('/root/.hermes/state.db')
   cur = conn.cursor()
   cutoff = time.time() - 86400
   cur.execute('''SELECT id, source, title, started_at FROM sessions
       WHERE started_at > ? AND source != \"cron\"
       ORDER BY started_at DESC LIMIT 10''', (cutoff,))
   for r in cur.fetchall():
       print(f'{r[0][:20]} | {r[1]} | {str(r[2])[:60]} | {r[3]}')
   conn.close()
   "
   ```
   This is the **only reliable way** to filter by session source.

3. **Find error/incident sessions** (FTS5): `session_search(query="error OR crash OR fail OR OOM OR gateway", sort="newest", limit=5)`
   Works well — these keywords are rare in normal messages.

4. **Find user conversations** (FTS5): `session_search(query="je OR tu OR merci OR bonne nuit", sort="newest", limit=5)`
   French pronouns/courtesies are strong signals of interactive sessions.

5. **Scroll into a specific session**: Use `session_search(session_id="...", around_message_id=N)`. If the ID from `state.db` doesn't work, try the full hex-suffixed form (e.g., `20260610_215606_7184f8b6` instead of `20260610_215606_7184`).

**Key pitfall:** Most sessions in a 24h window will be cron-sourced. The `source` field distinguishes `"cron"` from interactive sources (CLI, Discord, Telegram, etc.), but `session_search()` cannot filter by it — use the SQL fallback above. For session content, read messages directly from `state.db`:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/.hermes/state.db')
cur = conn.cursor()
cur.execute('SELECT id, role, substr(content,1,200) FROM messages WHERE session_id=? ORDER BY id LIMIT 8', ('FULL_SESSION_ID',))
for r in cur.fetchall():
    print(f'[{r[0]}] {r[1]}: {r[2]}')
conn.close()
"
```

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

## Cron Output Directory Growth

**Path:** `/root/.hermes/cron/output/`

Cron job output files accumulate unbounded. High-frequency jobs produce the most volume:
- A job running every 2 minutes produces 720 files/day × 365 = 262,800 files/year
- Even 160-byte files consume ~4 KB each on ext4 (inode + directory entry), so 720 files/day ≈ 2.9 MB/day in filesystem overhead alone
- At observed rates (89 MB across 20 job directories over 8 days), this grows ~10 MB/day

**Check current usage:**
```bash
du -sh /root/.hermes/cron/output/
du -sh /root/.hermes/cron/output/*/ | sort -rh | head -10
```

**Retention policy (recommended):**
Keep last 3 days per job, purge older:
```bash
python3 -c "
import os, glob, time
base = '/root/.hermes/cron/output'
cutoff = time.time() - 3 * 86400  # 3 days
removed = 0
for job_dir in glob.glob(f'{base}/*/'):
    for f in glob.glob(f'{job_dir}/*.md'):
        if os.path.getmtime(f) < cutoff:
            os.unlink(f)
            removed += 1
print(f'Removed {removed} files older than 3 days')
"
```

**Key pitfall:** Don't apply retention to all jobs equally. Daily reports (Morning Report, Daily Reflection) produce one 6 KB file/day — negligible. The 2-min kanban dispatchers produce 720 files/day at 160 bytes each — the directory entry overhead dwarfs the content. Prioritize cleaning dispatcher output directories first.

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

## Systemd Service Health

Check for crash loops and services stuck in restart cycles. A restart counter above 100 is a signal that something is broken and needs attention — not just a transient failure.

```bash
# List failed hermes-related services
systemctl --failed --no-legend | grep -i hermes || echo "no failed units"

# Check restart counters and uptime for hermes services
systemctl list-units --all --no-legend 'hermes-*' 2>/dev/null | while read -r unit _; do
  echo "--- $unit ---"
  # Show active state, substate, and any status detail
  systemctl status "$unit" --no-pager -l 2>/dev/null | head -8
  echo
done
```

**Red flags to escalate:**
- Restart counter > 100 (found with `systemctl show <unit> -p NRestarts`)
- Service in `failed` state with `active (exited)` parent but no running process
- `ExecStartPre=` or `ExecStartPost=` failures logged in journal

**Common root causes found in the wild:**
- **Port conflict**: A manually-started process (e.g., `hermes dashboard --insecure`) holds a port that the systemd service also tries to bind. Detect with `ss -tlnp | grep <port>` and compare the PID to the systemd-managed PID.
- **Stale PID file**: A previous instance left a PID file that makes the new instance think it's already running.

```bash
# Find what's holding a port (e.g., 9119 for dashboard)
ss -tlnp | grep 9119
# Cross-reference with systemd-managed PIDs
systemctl show hermes-dashboard.service -p MainPID
```

## Zombie Process Check

Defunct (zombie) processes consume PID slots but no RAM. They indicate a parent process that isn't calling `waitpid()` on terminated children. A few zombies are noise; accumulation over days signals a bug.

```bash
# Count hermes zombies
ps aux | awk '$8 ~ /Z/ && /hermes/' | wc -l

# Show zombie details (PID, parent, age)
ps -eo pid,ppid,stat,start,comm | awk '$3 ~ /Z/ && /hermes/ {print}'
```

**Escalate when:** > 3 zombies OR any zombie older than 24h. The parent process (PPID column) should be investigated — it's failing to reap children.

**Known pattern:** The Hermes gateway (PID of `hermes_cli.main gateway run`) may spawn short-lived worker processes. If it doesn't handle SIGCHLD with `waitpid()`, zombies accumulate.

## Cron Output Analysis — Silent Failure Detection

**Path:** `/root/.hermes/cron/output/<job_id>/`

Each cron job has its own output directory. Output files follow the pattern `YYYY-MM-DD_HH-MM-SS.md`.

**Key pitfall:** Exit-code monitoring is insufficient. A cron job can produce 0-byte output files while returning exit code 0 — the status dashboard shows "ok / silent (empty output)" which is indistinguishable from healthy watchdogs that are genuinely silent. Agent-based cron jobs that hit security scanner blocks (e.g., `pending_approval` on pipe-to-interpreter) will produce empty output while exiting cleanly.

**Silent failure detection (run during Morning Report):**

```bash
# Find jobs with recent consecutive zero-byte outputs (>10 in a row signals trouble)
python3 -c "
import os, glob
base = '/root/.hermes/cron/output'
for job_dir in sorted(glob.glob(f'{base}/*/')):
    jid = os.path.basename(job_dir.rstrip('/'))
    files = sorted(glob.glob(f'{job_dir}/2026-06-1[56]_*.md'))
    # Check last 20 files: how many are zero-byte?
    recent = files[-20:]
    if recent:
        zeros = sum(1 for f in recent if os.path.getsize(f) == 0)
        if zeros >= 15:
            # Read one to see if it's truly empty or just has no useful content
            sample = open(recent[-1]).read(200) if os.path.getsize(recent[-1]) > 0 else '(empty)'
            print(f'{jid:16s} | {zeros}/{len(recent)} zero-byte | sample: {sample[:100]}')
"
```

**Red flags:**
- >10 consecutive 0-byte outputs from an agent-based job (not a script watchdog)
- Last non-zero output is >6 hours old
- Agent jobs that normally produce reports suddenly going silent

**Benchmark:** Script-based watchdogs (CI, Memory, CPU, Gateway, Pre-Spawn Health) are *expected* to produce empty output when healthy — silence = nothing to report. Agent-based jobs (Block Watchdog, Morning Report, Digest) should NEVER produce empty output — silence = failure.

## Temporary File Cleanup

Check `/tmp` for stale Hermes artifacts that weren't cleaned up after cron jobs or backups.

```bash
# Show Hermes-related /tmp usage
du -sh /tmp/hermes-* 2>/dev/null | sort -rh
```

**Patterns to flag:**
- `hermes-backup-tmp` directories over 500M — likely from interrupted backup rotations
- `hermes-critical-*.tar.gz` files older than 48h — backup tarballs that should have been pruned
- `hermes-results` growing unboundedly — persisted tool output that the cleaner didn't remove

**Safe cleanup** (only remove artifacts older than 48h):
```bash
find /tmp -name 'hermes-critical-*.tar.gz' -mtime +2 -delete
find /tmp -name 'hermes-backup-tmp' -type d -mtime +2 -exec rm -rf {} + 2>/dev/null
```

**Key pitfall:** Don't blindly `rm -rf /tmp/hermes-*` — active sessions may still be writing there. Use `-mtime +2` as a safety gate.
