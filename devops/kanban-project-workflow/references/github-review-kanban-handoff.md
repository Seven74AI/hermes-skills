# Kanban Handoff After GitHub Review

The `github-code-review` skill (bundled) describes how to review PRs and approve
them on GitHub. It ends at "Step 9: Clean up" with no kanban awareness.

When running as a **kanban reviewer**, you MUST bridge this gap by adding kanban
handoff steps after the GitHub review is complete.

## The Gap

| Step | `github-code-review` says | Kanban reviewer MUST also |
|------|--------------------------|--------------------------|
| After APPROVE | `gh pr review --approve` | `kanban_unblock(coder_id)` THEN `kanban_complete(approved=true)` |
| After REQUEST_CHANGES | `gh pr review --request-changes` | `kanban_comment(feedback)` THEN `kanban_block("changes-requested")` |
| After cleanup | `git checkout main; git branch -D` | Nothing — cleanup is fine |

## Why this matters

3 out of 3 reviewers on 2026-07-07 approved PRs on GitHub and called
`kanban_complete(approved=true)` but **never unblocked the coder**. The coders
sat in `blocked` state indefinitely. Root cause: `github-code-review`'s scope
ends at GitHub, and the kanban handoff instructions in `kanban-project-workflow`
and the reviewer SOUL.md were not prominent enough to override the skill's
workflow.

## Correct Pattern

```python
# After approving the PR on GitHub:
terminal(f"hermes kanban --board {board} unblock {coder_task_id}")
kanban_complete(
    summary=f"Reviewed PR #{pr_number}; approved",
    metadata={"approved": True}
)
```

The `kanban-project-workflow` skill (v1.19.0+) includes this in the reviewer
step-by-step at the APPROVE path. Load it alongside `github-code-review`.
