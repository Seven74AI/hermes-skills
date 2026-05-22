# Fork Main Merge Gap — Diagnosis & Recovery

Workers complete tasks, create upstream PRs, but never merge into fork `main`.
Result: code on orphaned feature branches, fork main stale.

## Diagnosis

Check if PR feature branches are merged into fork main:

```bash
# For each open PR on upstream (mnlamart), check merge status on fork (Seven74AI)
for pr in $(gh api "repos/mnlamart/REPO/pulls?state=open" --jq '.[].number'); do
  SHA=$(gh api "repos/mnlamart/REPO/pulls/$pr" --jq '.head.sha')
  BRANCH=$(gh api "repos/mnlamart/REPO/pulls/$pr" --jq '.head.ref')
  # GH API compare: is SHA ahead of fork main? ahead > 0 = unmerged
  result=$(gh api "repos/Seven74AI/REPO/compare/main...${SHA}" --jq '"behind:\(.behind_by) ahead:\(.ahead_by)"')
  echo "PR #$pr ($BRANCH): $result"
done
```

Ahead > 0 means the branch has commits NOT in fork main → unmerged.
Behind is the fork main staleness (commits on main that the branch doesn't have).

## Recovery

For each unmerged branch, create a merge ticket:

```bash
# Using hermes CLI (shop board example)
BODY="Branche: feat/t_XXX | PR upstream: mnlamart/shop#N | Review: done | behind:X ahead:Y
Tache: rebase sur main, push, PR interne Seven74AI/shop, merge squash, bloquer pour review"
hermes kanban --board shop create "[MERGE] PR #N - <description> -> Seven74AI/shop main" --assign coder --body "$BODY"
```

## Real example — shop (2026-05-21)

After closing 4 ghost PRs on mnlamart/shop, the fork main was 226 commits ahead
and 5 commits behind upstream. The fork had 7 internal PRs (Seven74AI/shop → fork
main) that were approved but never merged:

| PR | Status | Content |
|----|--------|---------|
| #110 | 0 reviews | Fix all tests + flaky — CI green |
| #112 | ✅ Approved | Checkout flow i18n |
| #130 | ✅ Approved | Reviewer feedback fixes |
| #135 | 0 reviews | Invoice generation |
| #139 | 0 reviews | i18n FR+EN |
| #123 | 0 reviews | Return queries + Stripe refund v2 |
| #127 | 0 reviews | Return queries + Stripe refund v3 |

All PRs were worker-created and review-approved but NEVER merged into fork main.
A consolidation ticket (`t_533d2ebb`) handled pulling upstream + merging all work
into a single PR to upstream.
