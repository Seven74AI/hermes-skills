# Kanban Notification Subscriptions

The Kanban gateway delivers task events (blocked, completed, promoted, commented, spawned,
crashed, etc.) to subscribed channels. **Zero subscriptions by default** — no notifications
are sent until you explicitly subscribe.

## How it works

```
Worker blocks task → gateway emits "blocked" event → checks kanban_notify_subs → delivers to Telegram/Discord
```

The `kanban_notify_subs` table in each board's `kanban.db` controls which tasks notify which channels.

## Schema

```sql
CREATE TABLE kanban_notify_subs (
    task_id          TEXT NOT NULL,
    platform         TEXT NOT NULL,  -- 'telegram' | 'discord'
    chat_id          TEXT NOT NULL,  -- platform-specific chat/channel ID
    thread_id        TEXT DEFAULT '',
    user_id          TEXT,           -- creator reference
    notifier_profile TEXT,           -- which gateway profile delivers (default: None = active)
    created_at       INTEGER,
    last_event_id    INTEGER DEFAULT 0,
    PRIMARY KEY (task_id, platform, chat_id, thread_id)
);
```

`last_event_id` tracks delivery — only events with `id > last_event_id` are sent.
Set to 0 to replay from the beginning, or to the current max event id to start fresh.

## CLI

```bash
# Subscribe a task
hermes kanban --board <board> notify-subscribe <task_id> \
  --platform telegram --chat-id 1811944606

# With Telegram topic
hermes kanban --board <board> notify-subscribe <task_id> \
  --platform telegram --chat-id -1001234567890 --thread-id 17585

# Discord
hermes kanban --board <board> notify-subscribe <task_id> \
  --platform discord --chat-id 1506466871547924580

# List subscriptions
hermes kanban --board <board> notify-list
hermes kanban --board <board> notify-list --json

# Unsubscribe
hermes kanban --board <board> notify-unsubscribe <task_id> \
  --platform telegram --chat-id 1811944606
```

## Batch subscription (SQL)

```sql
-- Subscribe all active tasks to Telegram
INSERT OR IGNORE INTO kanban_notify_subs 
  (task_id, platform, chat_id, created_at, last_event_id)
SELECT id, 'telegram', '1811944606', CAST(strftime('%s','now') AS INTEGER), 0
FROM tasks WHERE status NOT IN ('done','archived');

-- Unsubscribe everything
DELETE FROM kanban_notify_subs;
```

## Event types delivered

**All event kinds** are delivered — no per-type filtering exists:

`blocked`, `completed`, `promoted`, `commented`, `spawned`, `crashed`, `claimed`,
`timed_out`, `gave_up`, `unblocked`, `reclaimed`, `archived`, `heartbeat`, etc.

No way to subscribe to only `blocked` + `completed` — it's all or nothing per task.

## Current state (as of 2026-05-20)

| Board | Telegram | Discord |
|-------|----------|---------|
| shop | 22 tasks → Home (1811944606) | 0 |
| Others | ? | ? |

## Delivery mechanism

- `notifier_profile` is `None` → the active gateway profile delivers
- If multiple gateways are running, the one that processed the event delivers it
- For Telegram topics, use `--chat-id` with the chat ID and `--thread-id` with the message thread ID
