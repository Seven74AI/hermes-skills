# GitHub Issue Closure After Kanban Task Completion

## The Gap

The Matt Pocock skills (`to-issues`, `implement`, `code-review`, `triage`) are silent on closing GitHub issues after implementation:

- **`to-issues`**: "Do NOT close or modify any parent issue" — only addresses the *parent*, not the children
- **`implement`**: "Commit your work to the current branch" — no mention of issues
- **`code-review`**: Reviews diffs — no mention of issue lifecycle
- **`triage`**: State machine ends at `ready-for-agent` — no "done/closed" transition

This creates a systematic blind spot: kanban coder tasks complete, PRs merge, but the corresponding GitHub issues stay open indefinitely.

## Rule

When a coder kanban task that references a GitHub issue completes (PR merged, CI green, reviewer approved), the coder MUST close the referenced GitHub issue.

- If the PR body includes `Fixes #NN` or `Closes #NN`, GitHub auto-closes on merge — **verify it actually happened**
- If the PR only references the issue without a closing keyword (e.g., "GitHub #48"), close it manually:
  ```bash
  gh issue close <number> --repo <owner>/<repo>
  ```

Do this as part of `kanban_complete` — check the issue is closed before marking the task done.

## Detection Pattern

After completing a batch of slices on a board, cross-reference done kanban tasks against open GitHub issues:

```bash
# List open issues
gh issue list --repo <owner>/<repo> --state open --json number,title --limit 100

# Cross-reference with kanban done tasks
hermes kanban --board <board> list --json | \
  python3 -c "import sys,json; [print(t['title'][:80]) for t in json.load(sys.stdin) if t['status']=='done']"
```

Any issue whose corresponding slice is fully done (coder task + reviewer task both completed) should be closed.

## Observed

music-library board 2026-07-07 — issues #40 through #46 all open despite all 7 corresponding slices having completed coder + reviewer tasks and merged PRs. The `to-issues` parent guard was correctly applied (parent #38/39 left open), but nobody closed the children. Seven issues, ~5 min to close with `gh issue close`.
