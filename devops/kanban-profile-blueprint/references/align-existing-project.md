# Align Existing Project with Shop Standards

When bringing an existing project up to the same operational standards as Shop
(branch protection, CI gates, watchdogs, cleanup sweep).

## Audit Checklist

Run these checks first to identify gaps:

```bash
REPO="music-library"  # or whichever project

# 1. Branch protection on fork
gh api repos/Seven74AI/$REPO/branches/main/protection \
  --jq '{approvals: .required_pull_request_reviews.required_approving_review_count, contexts: .required_status_checks.contexts}'

# 2. Auto-merge on fork
gh api repos/Seven74AI/$REPO --jq '{auto_merge: .allow_auto_merge, delete_branch: .delete_branch_on_merge}'

# 3. Fork Actions enabled
gh api repos/Seven74AI/$REPO/actions/permissions --jq '{enabled: .enabled, allowed: .allowed_actions}'

# 4. CI workflow — check BOTH fork AND upstream for silent bypasses
# Fork:
curl -s https://raw.githubusercontent.com/Seven74AI/$REPO/main/.github/workflows/deploy.yml \
  | grep -n '|| true\|--if-present\|typecheck'
# Upstream:
curl -s https://raw.githubusercontent.com/mnlamart/$REPO/main/.github/workflows/deploy.yml \
  | grep -n '|| true\|--if-present\|typecheck'

# 5. Watchdogs — global ones cover all projects, but verify they exist
cronjob list | grep -E '(CI Watchdog|Block Watchdog|Pre-Spawn)'

# 6. Package manager divergence
curl -s https://raw.githubusercontent.com/Seven74AI/$REPO/main/package.json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('packageManager','npm'))"
curl -s https://raw.githubusercontent.com/mnlamart/$REPO/main/package.json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('packageManager','npm'))"
```

## Standard Fixes

### Branch protection + auto-merge

```bash
# Auto-merge
gh api --method PATCH repos/Seven74AI/$REPO \
  -F allow_auto_merge=true -F delete_branch_on_merge=true

# Branch protection: 1 approve + CI contexts
gh api --method PUT repos/Seven74AI/$REPO/branches/main/protection --input - <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "typecheck", "vitest", "playwright-gate"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
EOF
```

### Fork Actions (one-time)

Already enabled for most projects. If not:
```bash
echo '{"enabled":true,"allowed_actions":"all"}' | \
  gh api --method PUT /repos/Seven74AI/$REPO/actions/permissions --input -
```

### Watchdogs

Watchdogs are **global** — they cover all boards automatically. No per-project setup needed.
- CI Watchdog (light): every 2min, unblocks when CI passes + auto-merge completes
- Kanban Block Watchdog: every 5min, handles review deadlocks
- Pre-Spawn Health Watchdog: every 5min, pre-spawns workers

### Cleanup Sweep PR

Standard cleanup for a project being brought up to shop parity:

1. Fix `--if-present` → remove it (or `|| true` → remove it)
2. Add `test:all` script to `package.json`:
   ```json
   "test:all": "npm run typecheck && vitest run && npm run test:e2e:run"
   ```
3. Add `CONTRIBUTING.md` with AI worker quickstart
4. Create PR with auto-merge enabled

### Upstream `|| true` Fix

If upstream has `|| true` on typecheck:
```bash
# Clone fork, create branch tracking upstream/main
git remote add upstream https://github.com/mnlamart/$REPO.git
git fetch upstream main
git checkout -b fix/upstream-typecheck upstream/main

# Fix and push
sed -i 's/pnpm typecheck || true/pnpm typecheck/' .github/workflows/deploy.yml
git commit -am "fix: remove ||true from typecheck CI step"
git push origin fix/upstream-typecheck

# Create PR from fork → upstream
gh pr create --repo mnlamart/$REPO --base main --head Seven74AI:fix/upstream-typecheck \
  --title "fix: remove ||true from typecheck CI step" \
  --body "Same regression found and fixed on shop."
```

## Pitfalls

- **Fork/upstream package manager divergence**: fork may use npm while upstream uses pnpm.
  When creating PRs from fork → upstream, ensure workflow changes preserve the upstream's package manager commands.
- **`--if-present` = `|| true`**: both patterns silently skip typecheck. `--if-present` is npm-specific;
  `|| true` is shell-generic. Both must be removed. Check BOTH repos.
- **`test:all` script**: if missing, workers run tests inline and burn 50-200 turns. Add it to every project.
