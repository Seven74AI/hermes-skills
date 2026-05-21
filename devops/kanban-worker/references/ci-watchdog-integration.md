# CI Watchdog Integration for Workers

How workers interact with the CI watchdog (`ci-watchdog.py`, cron every 2 min).

## When to use

Any coding task that opens a GitHub PR and needs CI verification before the task
can be marked complete. The CI watchdog watches for kanban-labeled PRs, checks
CI status, and merges or reports failure — all without human intervention.

## Worker workflow

```
1. Implement → git push branch
2. Create PR on fork WITH kanban label
3. Block with "awaiting CI: PR label kanban:<TASK_ID>"
4. CI watchdog finds PR by label → checks CI
5. CI green? → watchdog merges, deletes PR URL comments, unblocks you
6. CI red?   → watchdog comments failure, unblocks you → fix → repush → go to 1
```

## Step 2 — Creating the PR with label

```bash
# The critical part: --label "kanban:$HERMES_KANBAN_TASK"
gh pr create \
  --repo Seven74AI/REPO \
  --base main \
  --head feat/my-branch \
  --label "kanban:$HERMES_KANBAN_TASK" \
  --title "feat: summary of change"
```

The label is `kanban:` followed by the task ID (e.g. `kanban:t_6e0841f5`).
This is what the CI watchdog searches for.

## Step 3 — Blocking correctly

```python
kanban_block(
    reason="awaiting CI: PR label kanban:" + os.environ["HERMES_KANBAN_TASK"]
)
```

The reason MUST contain `awaiting CI` (CI watchdog searches `%awaiting CI%`)
AND `kanban:<TASK_ID>` (CI watchdog extracts the label to find the PR).

## Step 5/6 — After CI verdict

When the CI watchdog unblocks you (it comments `[CI-WATCHDOG] ...` on the task),
you re-spawn automatically. Your next run should:

- If CI green (comment says "merged"): verify the merge succeeded, then `kanban_complete`
- If CI red (comment says "CI failed"): read the error, fix the code, push again, create a new PR with the SAME kanban label, block again with "awaiting CI"

## NEVER post PR URLs in comments

The dispatcher's `check_respawn_guard()` scans ALL comments from the last 24h
for GitHub PR URLs matching `https://github.com/.../pull/N`. If found, the task
gets `respawn_guarded` with reason `active_pr` — blocked from spawning for 24h.

A comment containing `https://github.com/Seven74AI/shop/pull/95` will block the
task for 24h even after the PR is merged. The CI watchdog deletes these comments
after merging, but if you post a PR URL in a comment yourself, it may persist.

Use the LABEL, not the URL.

## Pitfall: gh pr list --label kanban: is broken

If you need to find your own PR by label (e.g. for verification), `gh pr list
--label kanban:` returns empty — `--label` does exact match, not prefix. Use jq
instead:

```bash
gh pr list --repo Seven74AI/REPO --state open \
  --json number,labels,headRefName \
  --jq '.[] | select(.labels[].name | startswith("kanban:")) | {number, labels: [.labels[].name], headRefName}'
```

## Pitfall: gh pr list --label kanban: is broken

If you need to find your own PR by label (e.g. for verification), `gh pr list
--label kanban:` returns empty — `--label` does exact match, not prefix. Use jq
instead:

```bash
gh pr list --repo Seven74AI/REPO --state open \
  --json number,labels,headRefName \
  --jq '.[] | select(.labels[].name | startswith("kanban:")) | {number, labels: [.labels[].name], headRefName}'
```

Also: `gh run view --repo X --log-failed` without a run URL prints help text,
not failure logs. Always pass the CI run URL: `gh run view <url> --log-failed`.

## All boards should label PRs

Even boards that use review-based gating (e.g. the-swarm), where workers block
with `review-required` instead of `awaiting CI`, should still add kanban labels
to their PRs. This future-proofs the board for CI watchdog adoption and gives
human operators visibility into which PR belongs to which task.

To add a board to the CI watchdog, add one line to `ci-watchdog.py`:

```python
BOARD_REPOS = {
    'shop':       'Seven74AI/shop',
    'the-swarm':  'Seven74AI/the-swarm',
    # Add new repos here  ← one line per board
}
```

## Notification model

The CI watchdog notifies Discord + Telegram only when it TAKES ACTION:

| CI state | Watchdog action | Notification? |
|---|---|---|
| CI running | Silent — check again in 2 min | No |
| CI green → merged | Comment + unblock | Yes |
| CI green → merge conflict | Comment + unblock | Yes |
| CI red | Comment failure logs + unblock | Yes |

You won't be notified for "CI still running" ticks — only when the verdict is in.
