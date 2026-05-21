# Light CI Watchdog — Design Notes

With GitHub auto-merge (`gh pr merge --auto --squash`), the watchdog no longer
merges PRs. Its only job: detect merged PRs → unblock kanban tasks.

## Implementation (~30 lines)

```python
#!/usr/bin/env python3
"""Poll merged PRs with kanban labels and unblock the corresponding tasks."""
import subprocess, re, os

BOARDS_FILE = os.path.expanduser("~/.hermes/kanban/.ci-watchdog-boards")
DEFAULT_BOARDS = ["shop", "the-swarm", "music-library", "baguette", "glance",
                   "videogame-lab", "edgee-lab"]

def get_boards():
    if os.path.exists(BOARDS_FILE):
        with open(BOARDS_FILE) as f:
            return [l.strip() for l in f if l.strip()]
    return DEFAULT_BOARDS

def get_repo(board):
    mapping = {
        "shop": "Seven74AI/shop",
        "the-swarm": "Seven74AI/the-swarm",
        "music-library": "Seven74AI/music-library",
        "baguette": "Seven74AI/baguette",
        "glance": "Seven74AI/glance",
        "videogame-lab": "Seven74AI/videogame-lab",
        "edgee-lab": "Seven74AI/edgee-lab",
    }
    return mapping.get(board)

def main():
    for board in get_boards():
        repo = get_repo(board)
        if not repo:
            continue
        # List merged PRs with kanban labels
        r = subprocess.run(
            ["gh", "pr", "list", "--repo", repo, "--state", "merged",
             "--label", "kanban:", "--json", "labels,number", "--limit", "20",
             "--search", "merged:>=1h"],
            capture_output=True, text=True
        )
        import json
        prs = json.loads(r.stdout) if r.stdout.strip() else []

        for pr in prs:
            for label in pr["labels"]:
                m = re.match(r"^kanban:(t_[a-f0-9]{8})$", label["name"])
                if m:
                    task_id = m.group(1)
                    subprocess.run(
                        ["hermes", "kanban", "--board", board, "unblock", task_id],
                        capture_output=True
                    )
                    print(f"Unblocked {task_id} on {board} (PR #{pr['number']})")

if __name__ == "__main__":
    main()
```

## Deployment

```bash
hermes cron create \
  --name "kanban CI unblock" \
  --schedule "every 2m" \
  --script kanban-ci-unblock.py \
  --no-agent \
  --deliver local
```

Uses `--no-agent` (script-only, no LLM) + `--deliver local` (no notification
when clean — the old watchdog sent Discord pings, but a simple unblock doesn't
need fanfare).

## Why `--search "merged:>=1h"`

GitHub's auto-merge has a small delay between approval+CI passing and the actual
merge. The 1h window is a safety buffer: merged in the last hour is recent
enough that the coder's task is still blocked but old enough that the merge
is definitely complete.

## Migration from old CI watchdog

Old cron: `10cb5de254d0`, every 2 min. Replace with this script.

Key differences:
- No `gh pr merge` call — GitHub auto-merge handles it
- No `--auto` flag management — coder sets it at PR creation
- No token tracking, no retry logic — unblock is idempotent
- No Discord delivery — silent when clean
