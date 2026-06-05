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

**Common OOM root cause**: kanban dispatch spawns too many coder workers
simultaneously (e.g., 15 coders after a large audit decomposition). Each coder
runs vitest, playwright, chrome-headless, npm, esbuild — 200-800MB each.
Quick fix: reduce `delegation.max_concurrent_children` on the coder profile.

See `references/oom-diagnosis-example.md` for a real-world case (2026-05-31).

## Kanban Dispatcher Tick Failures

When a kanban board shows 0 active workers but tasks exist, check for silent dispatcher
failures — the gateway ticks the board but the tick fails without crashing.

See `references/kanban-dispatcher-tick-failure.md` for diagnosis steps and a real-world case.

## Pitfalls

- **Flood control ≠ disconnected**: Telegram rate-limiting is transient.
  Restarting the gateway drops queued messages unnecessarily. Wait it out.
- **Dashboard `updated_at` is from gateway startup, not last platform activity**.
  A stale `updated_at` doesn't mean the platform is down — check logs instead.
- **Don't curl Telegram API without user approval** when the bot token is
  involved. Prefer Hermes-native diagnostics (logs, dashboard) first.
- **Kanban dispatcher failures are silent**: A board can be "active" (listed, DB OK)
  but receiving no workers because the dispatcher tick keeps failing. Check
  `/root/.hermes/logs/errors.log` for `kanban dispatcher.*tick failed` when a board
  seems idle despite having todo tasks.
