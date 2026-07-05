# PR Cleanup After Consolidation

When a big PR (like a dependency batch) has been merged and there are stale open
PRs that are now partially or fully superseded.

## Step 1: List all open PRs

```bash
gh pr list --repo ORG/REPO --state open \
  --json number,title,headRefName,statusCheckRollup,createdAt,url
```

## Step 2: Check what's already on main

For each open PR, check if its changes are already on main:

```bash
# Check if the PR's diff is empty (already applied)
gh pr diff $PR_NUM --repo ORG/REPO | head

# Check if specific changes exist on main
git diff main -- the/file/changed.ts
```

Common cases:
- **PR changes already on main** → the PR was merged via a consolidated PR
- **PR touches package-lock.json but repo now uses pnpm** → lockfile-only PR is irrelevant
- **PR bumps a dep that's already at target version on main** → already resolved
- **PR has changes NOT yet on main** → needs consolidation

## Step 3: Consolidate remaining changes

Create a single branch from main, apply only the remaining changes:

```bash
git checkout main && git pull
git checkout -b consolidate-all-deps
```

Apply each remaining change (patch, cherry-pick, or manual edit), then:

```bash
pnpm install  # regenerate lockfile if pnpm
# Run full CI locally:
pnpm lint && pnpm typecheck && pnpm test -- --run
# Fix any issues, commit, push, create PR
```

## Step 4: Close superseded PRs

```bash
# Close with explanation
gh pr close $PR --repo ORG/REPO -c "Superseded by consolidated PR #XX"

# If no write permission, at minimum comment:
gh pr comment $PR --repo ORG/REPO -b "Superseded by consolidated PR #XX — please close."

# Some PRs may already be autoclosed by renovate
```

## Pitfalls

- **Don't assume all open PRs need action** — check main branch first. Half may already be resolved.
- **Lockfile-only PRs on npm are irrelevant after pnpm migration** — `package-lock.json` diffs are dead.
- **Renovate PRs may be auto-closed** — check state before trying to close.
- **You may not have close-permission on upstream** — fall back to commenting.
