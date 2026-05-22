# Light CI Watchdog — Simplified (unblock-only)

Replaces the old CI watchdog that merged PRs AND unblocked tasks.
With GitHub native auto-merge (`gh pr merge --auto`), the watchdog
only needs to detect merged PRs and unblock corresponding kanban tasks.

## Why simpler

Old watchdog did 3 things:
1. Check CI status on PRs with kanban labels
2. Merge if CI green
3. Unblock kanban task

GitHub auto-merge now handles #1 and #2. The watchdog only does #3.

## Script (~30 lines)

```python
#!/usr/bin/env python3
"""Detect merged PRs with kanban labels, unblock corresponding tasks."""
import subprocess, re, sqlite3, json

BOARDS = {
    "shop": "Seven74AI/shop",
    "the-swarm": "Seven74AI/the-swarm",
}

for board, repo in BOARDS.items():
    result = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--state", "merged",
         "--limit", "20", "--json", "labels,number",
         "--search", "label:kanban:"],
        capture_output=True, text=True
    )
    prs = json.loads(result.stdout)

    db = sqlite3.connect(f"/root/.hermes/kanban/boards/{board}/kanban.db")

    for pr in prs:
        for label in pr["labels"]:
            m = re.match(r"kanban:(t_[a-f0-9]+)", label["name"])
            if m:
                task_id = m.group(1)
                cur = db.execute(
                    "SELECT status FROM tasks WHERE id=? AND status='blocked'",
                    (task_id,)
                )
                if cur.fetchone():
                    subprocess.run(
                        ["hermes", "kanban", "--board", board,
                         "unblock", task_id]
                    )
                    print(f"Unblocked {task_id} (PR #{pr['number']} merged)")
    db.close()
```

## Cron job

```bash
hermes cron create \
  --name "CI watchdog (light)" \
  --schedule "every 2m" \
  --script ~/.hermes/scripts/ci-watchdog-light.py \
  --no-agent \
  --deliver local
```

`--no-agent`: pure script, no LLM call. `--deliver local`: silent when clean
(empty stdout = no delivery).

## Differences from old watchdog

| | Old | Light |
|---|---|---|
| Merges PRs | Yes (`gh pr merge`) | No (GitHub auto-merge) |
| Checks CI status | Yes (poll checks API) | No |
| Unblocks tasks | Yes | Yes |
| Code size | ~200 lines | ~30 lines |
| Rate limit risk | High (checks API per PR) | Low (one `gh pr list`) |
