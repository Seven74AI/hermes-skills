# Ghost PR Cleanup

Stale worker-created PRs accumulate on upstream repos over time. These PRs were
pushed by workers, never reviewed or merged, and became abandoned. Close them
in bulk.

## Recipe

```bash
# 1. List all open PRs from the fork on upstream
gh pr list --repo mnlamart/REPO --state open \
  --json number,title,headRefName,createdAt,headRepositoryOwner \
  --jq '.[] | select(.headRepositoryOwner.login=="Seven74AI") | "#\(.number) \(.title) [\(.headRefName)]"'

# 2. Review each: check if mergeable, has reviews, still relevant
for n in <PR_NUMBERS>; do
  gh pr view $n --repo mnlamart/REPO --json mergeable,reviews,labels
done

# 3. Close them all
for n in <PR_NUMBERS>; do
  gh pr close $n --repo mnlamart/REPO --comment "Ghost PR — fermé lors du cleanup."
done

# 4. Clean up branches on the fork (if they still exist)
for b in <BRANCH_NAMES>; do
  gh api -X DELETE "repos/Seven74AI/REPO/git/refs/heads/$b"
done
```

## Real example — shop (2026-05-21)

4 ghost PRs closed on mnlamart/shop, all from Seven74AI fork, 0 reviews:

| PR | Branch | Status |
|----|--------|--------|
| #197 | feat/t_11e11c-v7 | Invoice PDF download |
| #194 | feat/i18n-consolidated | i18n FR+EN |
| #184 | feat/t_1bf9af | Invoice generation (CONFLICTING) |
| #182 | feat/adr-005-sqlite-scaling-cliff | ADR 005 |

All branches were already deleted on the fork.

## Prevention

After a consolidation PR merges into upstream, any remaining open PRs from the
fork become ghosts. Always audit and close them as part of the consolidation
workflow.
