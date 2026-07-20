# PR Auto-Merge Pitfalls

Two silent failure modes discovered 2026-07-13 on music-library board.

## 1. Review dismissal on rebase + force-push

When you rebase and force-push to an approved PR branch, GitHub **dismisses all prior
approvals**. `reviewDecision` becomes `REVIEW_REQUIRED` even for identical code.
Auto-merge (enabled, CI green) silently does nothing — the PR sits unmerged.

**Symptoms:**
- `gh pr view <N> --json mergeStateStatus` = `BLOCKED`
- `gh pr view <N> --json reviewDecision` = `REVIEW_REQUIRED`
- `gh pr view <N> --json reviews` shows prior approvals as `DISMISSED`

**Observed:** PR #105 (music-library): approved → rebased to fix CONFLICTING →
force-pushed → review DISMISSED → CI all green but auto-merge blocked for hours.

**Prevention:**
```bash
# After every rebase + force-push, verify:
gh pr view <N> --json reviewDecision,reviews --jq '{decision: .reviewDecision, reviews: [.reviews[] | {author: .author.login, state: .state}]}'
```
If `REVIEW_REQUIRED`, request re-review or trigger the kanban reviewer.

## 2. Late-arriving commits on consolidation PRs

When creating a consolidation PR from fork to upstream, commits can land on
origin/main between branch creation and CI completion. The consolidation branch
becomes stale, missing critical fixes.

**Observed:** consolidation PR #72 (upstream): created with 50 commits, but
PR #168 (MSW mock fix + dummy audio files) landed on origin/main 5 minutes
after branch creation. CI failed on a flaky test that #168 fixed.

**Recovery:**
```bash
git checkout consolidation/sync-YYYYMMDD
git merge origin/main --no-edit   # fast-forward to include late arrivals
git push origin consolidation/sync-YYYYMMDD
# PR auto-updates, CI re-runs with the fix
```

**Prevention:** Before creating the consolidation PR, verify no CI is in flight:
```bash
gh pr list --repo Seven74AI/music-library --json number,statusCheckRollup --jq '.[] | select(.statusCheckRollup != null) | .number'
```
Wait for all in-flight PRs to merge, then create the consolidation.
