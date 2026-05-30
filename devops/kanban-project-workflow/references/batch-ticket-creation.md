# Batch Kanban Ticket Creation via execute_code

When you need to create 10+ tickets at once (e.g., decomposing a research report into implementation tasks), the CLI one-at-a-time approach is slow and repetitive. Use `execute_code` with `terminal()` calls in a loop.

## Pattern

```python
from hermes_tools import terminal

TICKETS = [
    ("assignee_name", "Title", "Body text with full description"),
    ("coder", "[P0] Fix critical bug", "Detailed instructions..."),
    # ... more tickets
]

for assignee, title, body in TICKETS:
    priority = {"[P0]": "1", "[P1]": "2", "[P2]": "3"}.get(title[:4], "3")

    cmd = f"""hermes kanban --board <board> create \
  --assignee {assignee} \
  --max-runtime 3600s \
  --priority {priority} \
  --skill <project> --skill kanban-project-workflow \
  --body {repr(body)} \
  {repr(title)}"""

    result = terminal(cmd)
    for line in result["output"].split("\n"):
        if "Created" in line:
            task_id = line.split()[1]
            print(f"  {task_id}: {title[:80]}")

print(f"\nTotal: {len(TICKETS)} tickets created")
```

## Notes

- `repr()` handles escaping of quotes, newlines, and special characters in body/title strings
- Priority auto-derived from `[PX]` prefix in title
- Always include `kanban-project-workflow` in skills to prevent red-CI merges
- After creation, dispatch with `hermes kanban --board <board> dispatch`
- For Telegram notifications on all tickets, DB direct insert is faster than CLI per-ticket:
  ```python
  import sqlite3
  db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
  for tid in task_ids:
      db.execute("INSERT OR IGNORE INTO task_subscriptions (task_id, platform, chat_id) VALUES (?, ?, ?)",
                 (tid, 'telegram', '<chat_id>'))
  db.commit()
  ```

## When to use

- Decomposing research reports into 10+ implementation tickets
- Creating parallel coder tickets for independent vertical slices
- Gap analysis → ticket creation in one shot

## When NOT to use

- 1-3 tickets — just use `hermes kanban create` directly
- Tasks that need a planner to decompose first — let the planner create child tickets naturally
