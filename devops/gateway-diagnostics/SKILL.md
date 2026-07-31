---
name: gateway-diagnostics
description: Diagnose Hermes gateway issues — unresponsive platforms, message delivery failures, connection drops, and health checks.
platforms: [linux]
---

# Gateway Diagnostics

Use this skill when a messaging platform (Telegram, Discord) seems unresponsive, messages aren't being delivered, or the gateway reports connection errors.

## Quick health check

1. Gateway process status:
   ```bash
   systemctl status hermes-gateway
   hermes gateway status
   ```
2. Dashboard API (platform states):
   ```bash
   curl -s http://localhost:9119/api/status | python3 -m json.tool
   ```
   Key fields: `gateway_platforms.<platform>.state` (should be `connected`),
   `gateway_platforms.<platform>.error_message`, `active_sessions`.

3. Memory/swap pressure:
   ```bash
   systemctl show hermes-gateway | grep -E "Memory(Swap)?(Current|Peak)"
   ```
   High swap usage (>500M) with elevated peak indicates OOM pressure.
   Peak >5GB with current ~800MB is normal for long-running sessions.

## Platform-specific diagnostics

### Telegram "not responding"

The most common cause is **Telegram flood control** — the gateway hits rate limits and messages queue up.

1. Check for flood control in logs:
   ```bash
   journalctl -u hermes-gateway --since "4 hours ago" --no-pager | grep -i telegram
   ```
   Look for: `WARNING gateway.platforms.telegram: [Telegram] Telegram flood control, waiting X.Xs`
   See `references/telegram-flood-control-example.md` for a real-world example.

2. If no Telegram activity in logs for hours but the user sent messages recently,
   messages aren't reaching the gateway. Check webhook health:

   ```bash
   # Get webhook info from Telegram API
   TG_TOKEN=$(grep -oP 'TELEGRAM_BOT_TOKEN=\K\S+' /root/.hermes/.env | head -1)
   curl -s "https://api.telegram.org/bot$TG_TOKEN/getWebhookInfo" | python3 -m json.tool
   ```
   Verify: `pending_update_count`, `last_error_date`, `url` fields.
   If the webhook URL doesn't match the server's current address, it needs updating.

3. If flood control is recent (<2h), messages are likely queued and will deliver
   once the rate limit window clears. No action needed.

4. The gateway does **not** expose queue depth via the dashboard API currently.
   Absence of Telegram log lines after flood control means either (a) no new
   messages arrived or (b) webhook isn't delivering them. Test with a direct
   send to confirm.

### Discord "not responding"

1. Check for connection errors:
   ```bash
   journalctl -u hermes-gateway --since "1 hour ago" --no-pager | grep -i discord
   ```
   Look for: `disconnect`, `reconnect`, `heartbeat`, `session invalid`.

2. Discord reconnects are normally automatic. If `state` shows something other
   than `connected` in the dashboard API, restart the gateway:
   ```bash
   systemctl restart hermes-gateway
   ```

## Restart gateway

```bash
systemctl restart hermes-gateway
```
Restart clears message queues. Only do this when a platform is confirmed
disconnected (not just flood-controlled), as queued messages will be lost.

## OOM Diagnosis (when gateway restarts unexpectedly)

When the gateway restarts without an explicit command, suspect OOM:

```bash
# 1. Confirm OOM kills in dmesg
dmesg -T | grep -i "oom.*killed" | tail -5

# 2. Check gateway memory at time of crash
journalctl -u hermes-gateway --since "2 hours ago" --no-pager | \
  grep "memory peak\|swap peak" | tail -3

# 3. Count concurrent workers (each spawns vitest + playwright + chrome-headless)
systemctl status hermes-gateway --no-pager | grep "hermes.*kanban.*chat" | wc -l
```

**Common OOM root causes:**

1. **kanban coder workers**: dispatch spawns too many coder workers simultaneously (e.g., 15 coders after a large audit decomposition). Each runs vitest, playwright, chrome-headless, npm, esbuild — 200-800MB each. Quick fix: reduce `delegation.max_concurrent_children` on the coder profile.

2. **marker-pdf OCR (marker_single)**: a single scanned PDF book processed by marker-pdf can consume 10+ GB RSS and OOM-kill the gateway. Diagnosis: `dmesg -T | grep oom-kill` shows `task=marker_single` with `anon-rss:10000000+ kB`. The gateway logs show `Failed with result 'oom-kill'` and `Memory peak: 10.6G`. Mitigation: ensure OCR book tickets are chained with `--parent` so they run solo — see `book-extraction` skill. Real case 2026-06-14: 626-page scanned Fomenko PDF → marker_single 10.5 GB RSS → OOM killed gateway at 14h uptime, then again 7 min after restart on same task.

See `references/oom-diagnosis-example.md` for a real-world case (2026-05-31).

## Kanban Crash-Loop (repeated_crashes + protocol violation)

When `hermes kanban diagnostics` shows `repeated_crashes` counts in the hundreds
with "protocol violation: worker exited cleanly (rc=0) without calling
kanban_complete or kanban_block", it's a **race condition** between the dispatcher
and the worker:

1. Worker does the work, calls `kanban_complete`
2. Concurrent dispatcher tick resets the task (`running → ready`), changing `current_run_id`
3. `kanban_complete`'s `expected_run_id` guard rejects the completion — rowcount=0
4. Tool returns error in 0.0s, worker exits cleanly without completing
5. Dispatcher sees "protocol violation" → resets to `ready` → spawns new worker
6. Cycle repeats indefinitely

**Diagnosis:**
```bash
hermes kanban --board <board> diagnostics
# Look for: repeated_crashes=N, "pid not alive", "protocol violation"
```

**Fix:**
```bash
# CLI completion bypasses expected_run_id guard
hermes kanban --board <board> complete <task_id>
```

**Prevention:** when adding new books, scan PDFs with pymupdf before creating tickets.
If < 500 chars → scanned → do NOT create a kanban ticket (marker-pdf will OOM-loop).
Upload to MinIO and append to `/root/.hermes/queues/ocr_books.txt` instead.

## Dashboard Crash-Loop

When `hermes-dashboard.service` is in `activating (auto-restart)` with a climbing restart counter, it's typically a port conflict from a stale manual process. See `references/dashboard-crashloop-playbook.md` for the full diagnosis and fix (kill stale PID → restart).

## Kanban Board Recovery

When the dispatcher auto-disables a board due to DB corruption, or when WAL mode causes recurring index corruption, see `references/kanban-board-recovery.md` for recovery procedures (touch-to-re-enable, dump→restore, WAL→DELETE mode migration, 0-byte ghost DB detection).

## Firecrawl / Browser Tool Infrastructure

When Hermes browser tools fail with errors referencing internal URLs (e.g., `127.0.0.1:3002/tabs`), the issue is usually the self-hosted Firecrawl Docker stack. See `references/firecrawl-stack-health.md` for health checks and common failure modes (RabbitMQ queue corruption, browser endpoint 500s).

## Pitfalls

- **Flood control ≠ disconnected**: Telegram rate-limiting is transient.
  Restarting the gateway drops queued messages unnecessarily. Wait it out.
- **Dashboard `updated_at` is from gateway startup, not last platform activity**.
  A stale `updated_at` doesn't mean the platform is down — check logs instead.
- **Don't curl Telegram API without user approval** when the bot token is
  involved. Prefer Hermes-native diagnostics (logs, dashboard) first.
- **Stale profile API keys → silent worker crash-loops.** When an API key (DeepSeek, Anthropic, etc.) is rotated in `~/.hermes/.env`, Hermes profile `.env` files are NOT automatically updated. Workers under stale profiles die in ~4s with HTTP 401, the dispatcher respawns them, and the cycle repeats silently — hundreds of times before detection. Symptoms: a board has a running task that never completes, `last_error` shows auth errors, gateway logs fill with 401s. **Fix:** after any key rotation, run `bash /root/.hermes/skills/devops/token-compromise-response/scripts/sync-profile-keys.sh ALL`. See `token-compromise-response` → `references/profile-key-sync.md` for the full procedure. **Real case (2026-06-16):** 185 crash-loops over 4.5h, 6 of 8 profiles stale.

- **Leaked file descriptors → "database is locked" on cron scripts.** The gateway process holds open FDs to kanban DB files. Over time, these accumulate — `lsof -p <gateway_pid> | grep kanban.db` may show 4+ open FDs to the same DB. When a cron script (pre-spawn-watchdog, health checks) tries to open the same database, SQLite returns `database is locked` because the gateway's write lock is held. **Fix:** restart the gateway (`systemctl restart hermes-gateway`) to release leaked FDs. The watchdog script itself should use `sqlite3.connect(path, timeout=10)` with retry logic (see `pre-spawn-watchdog.py`). **Real case (2026-06-16):** gateway PID 978888 held 4 FDs to `knowledge-base/kanban.db`, causing persistent `database is locked` in the pre-spawn health watchdog and preventing dispatcher ticks since ~16:46.
  but receiving no workers because the dispatcher tick keeps failing. Check
  `/root/.hermes/logs/errors.log` for `kanban dispatcher.*tick failed` when a board
  seems idle despite having todo tasks.
- **Dashboard port conflict with systemd auto-restart**: systemd auto-restart cannot resolve port conflicts. If a manual process (e.g., old `hermes dashboard` invocation) holds the port, systemd cycles forever with `status=1/FAILURE` every 5 minutes — the old process never releases the port. Detection: `ss -tlnp | grep <port>` shows a PID different from the service's PID. Resolution: `kill <old_pid>` then `systemctl restart <service>`. Observed June 2026: dashboard in crash loop for 15 days (~5700 restarts) due to PID 100670 holding port 9119 from a manual run on May 30.
