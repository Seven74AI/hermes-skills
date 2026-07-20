# PR Orphan Cleanup — When Kanban Tasks Complete But PRs Stay Open

A kanban task completing (`done`/`archived`) does NOT automatically close its
GitHub PR. Common orphan patterns and cleanup procedures.

## Pattern 1: Task done but PR unmerged

The coder called `kanban_complete` but the PR is still open — unmerged, unreviewed,
or superseded. **This is a protocol violation** — coders must NOT complete a task
while its PR is unresolved.

**Detection:**
```bash
gh pr list --state open --json number,headRefName,title | python3 -c "
import json, sys, re
prs = json.load(sys.stdin)
for p in prs:
    m = re.search(r'(t_[a-f0-9]{6,8})', p['headRefName'])
    tid = m.group(1) if m else None
    print(f'PR #{p[\"number\"]}: ref={p[\"headRefName\"]} task={tid}')
"
```

**Cleanup per case:**
- **Superseded** (e.g. PR #142 replaced by PR #159): `gh pr close <N>`
- **CI green + review approved but unmerged**: `gh pr merge --auto --squash <N>` (NEVER `--admin`)
- **CI red + no review + task done**: premature task completion — investigate
- **Ghost PR (no task in DB)**: `gh pr close <N> --comment "Orphaned — task deleted from kanban"`

**Real case (2026-07-13, music-library):** 7 open PRs, 1 worker running, 5 tasks
done. PRs #142, #127, #112, #105 were orphaned — tasks completed but PRs never
merged or closed. Two PRs (#141, #139) had CI green + approved reviews but sat
unmerged because no one cleaned them up.

## Pattern 2: PR merged but task not cleaned up

PR was merged (via CI watchdog or manual), but the kanban task stayed in
`review-required` or `blocked`. The block watchdog should detect this pattern,
but stale claim_locks from the gateway can prevent it. See kanban-worker skill →
"Diagnosing dispatcher stuck" → Step 4 (stale claim_lock from gateway).

## Pattern 3: Multiple PRs for the same task

A task had multiple runs, each creating a new PR. The latest one is active;
older ones are stale. Close the stale ones and note the superseding PR in the
close comment.

## ⛔ Verification rule: check EVERY PR individually

When analyzing kanban task-to-PR mapping, do NOT assume from `gh pr list` alone.
Inspect each PR's full state before reporting conclusions:

```bash
for pr in <numbers>; do
  gh pr view $pr --json number,state,mergeable,mergeStateStatus,reviews,statusCheckRollup
done
```

`gh pr list` doesn't show CI results, review states, or merge conflicts.
A claim about PR status without individual inspection is unreliable.

**Real case (2026-07-13):** Agent claimed "5 PRs without review" based on task
status alone. Actual inspection revealed: 2 had approved reviews (#141, #139),
1 had CI failures not task issues (#127 typecheck), 1 had merge conflicts (#112),
and only 1 was genuinely unreviewed (#105). The incorrect claim was corrected
when the user demanded: "Do not assume, check every PR entirely."

## Pattern 4: Branch protection gaps (enforce_admins)

Workers can push directly to main when `enforce_admins` is `false` on branch
protection — even with required reviews configured. The admin bypass lets the
worker's token skip PR requirements entirely.

**Check:**
```bash
gh api repos/<owner>/<repo>/branches/main/protection --jq '.enforce_admins.enabled'
```

**Fix:**
```bash
gh api repos/<owner>/<repo>/branches/main/protection --method PUT \
  -f enforce_admins=true \
  -f required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}'
```

**Real case (2026-07-13, music-library):** commit `f9ed03d` introduced `<<<<<<< HEAD`
conflict markers in `.gitignore` via a direct push to main — bypassing all review.
The branch protection had `required_pull_request_reviews` set but `enforce_admins`
was `false`. The worker token had admin rights and skipped the PR requirement.
