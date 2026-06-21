# Cron Health Check — Methodology

## The rule

`last_status: ok` means the process exited cleanly. It does NOT mean the job accomplished its task. Always inspect the output file, not just the status line from `cronjob list`.

## Why

- Agent-based jobs can produce output that says "BLOCKED", "failed to write", "⚠️", or even "[SILENT]" while still exiting 0.
- No-agent scripts can crash mid-way but still exit 0 if the error is caught or the script handles it gracefully.
- Functional failures (Notion writes silently 404'd, delivery targets unreachable, data sources empty) don't affect exit codes.

## Method

1. `cronjob list` → get all jobs, filter to last 24h (`last_run_at`)
2. For each job that ran, read its latest output file from `/root/.hermes/cron/output/<job_id>/`
3. Scan for functional failure markers:
   - `BLOCKED` — integration/auth issue (Notion, Discord, GitHub)
   - `script failed` / `exit code` — no-agent script crashed
   - `⚠` / `WARN` — watchdog alert (may be expected, read context)
   - `Error` / `FATAL` — hard failure
   - `[SILENT]` — job produced nothing (suppressed delivery)
4. For jobs that deliver to external platforms (Discord, Notion, Telegram), verify the delivery actually happened — check the target (Notion DB, Discord channel) for the expected entry
5. **Special attention after token rotation**: Notion integrations lose DB connections when tokens are regenerated. Manually re-share the integration with ALL databases it needs to write to.
6. **Database liveness checks**: For any cron job that depends on a database file (kanban, session DB), verify the file is non-empty. A 0-byte `kanban.db` will pass all exit-code checks but silently prevent all ticket processing. Example: `[ -s /path/to/kanban.db ] || echo "CRITICAL: kanban.db is empty"`

## Watchdog alerts

Watchdog scripts (disk, memory, CPU, gateway) use WARN/CRIT thresholds. A ⚠️ in the output is the watchdog doing its job — read the context to determine if action is needed. Don't flag watchdog alerts as failures unless the value is at CRIT level or trending badly.

## Quick scan command

```bash
for d in /root/.hermes/cron/output/*/; do
  jid=$(basename "$d")
  latest=$(ls -t "$d"*.md 2>/dev/null | head -1)
  [ -z "$latest" ] && continue
  # Check if modified in last 24h
  [ "$(stat -c %Y "$latest")" -lt "$(date -d '24 hours ago' +%s)" ] && continue
  echo "=== $jid ==="
  grep -E 'BLOCKED|script failed|FATAL|⚠|WARN' "$latest" 2>/dev/null | head -3 || echo "  clean"
done
```
