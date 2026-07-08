# Cron-based notification watchdog for kanban tasks

When you need Telegram notifications on all child/reviewer tasks of a known
root task, but new tasks are created dynamically (e.g., coder creates reviewer),
a cron watchdog script handles auto-subscription.

## Pattern

1. Write a Python script that:
   - Lists all non-done tasks on the kanban board
   - Filters to tasks referencing the root task IDs (in title or body)
   - Checks existing subscriptions via `notify-list`
   - Subscribes Telegram for any task not already covered
   - Produces NO stdout when nothing changes (silent cron delivery)

2. Create a cron job:
   ```bash
   hermes cron create \
     --name "Audit notif watchdog — music-library" \
     --schedule "*/3 * * * *" \
     --script audit-notif-watchdog.py \
     --no-agent \
     --deliver telegram:...
   ```

3. With `no_agent=True` and silent-on-no-change script, the user only gets
   a message when a new subscription is actually created.

## Script template

```python
#!/usr/bin/env python3
"""Auto-subscribe Telegram notifications to linked tasks on a kanban board."""
import subprocess, os

PLATFORM = "telegram"
CHAT_ID = "Lieutner 7D (dm)"
BOARD = "music-library"
ROOT_TASKS = {"t_c1bbcb34", "t_ba7a484b"}

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip(), r.returncode

def get_all_tasks():
    out, _ = run(["hermes", "kanban", "--board", BOARD, "list"])
    return {line.split()[0] for line in out.splitlines() if line.startswith("t_")}

def is_subscribed(task_id):
    out, _ = run(["hermes", "kanban", "--board", BOARD, "notify-list", task_id])
    return f"{PLATFORM}:{CHAT_ID}" in out

target = f"{PLATFORM}:{CHAT_ID}"
for task_id in get_all_tasks():
    # Check if task references a root
    out, _ = run(["hermes", "kanban", "--board", BOARD, "show", task_id])
    if not any(root in out for root in ROOT_TASKS):
        continue
    if is_subscribed(task_id):
        continue
    stdout, rc = run([
        "hermes", "kanban", "--board", BOARD, "notify-subscribe", task_id,
        "--platform", PLATFORM, "--chat-id", CHAT_ID
    ])
    print(f"[NOTIF] Subscribed {target} to {task_id}: {stdout}")
# Silent when no action — no stdout = no delivery with no_agent=True
```

## Pitfalls

- **Script path must be relative** to `~/.hermes/scripts/` — just the filename,
  e.g. `--script audit-notif-watchdog.py`
- **`notify-subscribe` requires `--board` before the subcommand**, not after
- **Empty stdout = silent delivery** with `no_agent=True` — the script must
  produce zero output when nothing was subscribed
- **Re-subscribe after DB recovery** — if the `kanban_notify_subs` table is
  dropped (corruption recovery), all subscriptions are lost and the watchdog
  will re-subscribe on the next tick
