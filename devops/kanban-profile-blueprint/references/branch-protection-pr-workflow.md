# Branch Protection + PR Workflow

## Enable branch protection on main

```bash
gh api --method PUT /repos/OWNER/REPO/branches/main/protection \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["CI"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```

- `required_approving_review_count: 0` — allows kanban workers to self-merge after CI passes
- `strict: true` — branch must be up to date with main before merge
- `contexts: ["CI"]` — must match the job name in `.github/workflows/ci.yml`

## CI workflow requirements

The CI workflow must trigger on `pull_request` to `main`:

```yaml
on:
  pull_request:
    branches: [main]
```

The job name must match the protection context (e.g., `name: CI` → `contexts: ["CI"]`).

## Coder workflow

1. Workspace setup: embed token in git remote URL (see `references/token-embedding.md`)
2. `git checkout -b feat/TASK_ID`
3. Work, commit, push branch regularly
4. When done: `npm run test:all` in background+wait
5. If tests pass: `gh pr create --title "..." --base main --head $BRANCH`
6. `gh pr checks $BRANCH` — wait for CI
7. If CI passes: `gh pr merge $BRANCH --merge --delete-branch`

## Verification

After enabling protection, verify:
```bash
# Direct push to main should be rejected
git checkout main && echo "test" >> README.md && git add . && git commit -m "test" && git push origin main
# Should fail with: "remote: error: GH006: Protected branch update failed"
```

## Pitfalls

- **Protection is retroactive only** — commits already on main stay. Only NEW pushes are blocked.
- **CI job name mismatch** — if the workflow has `name: ci` (lowercase) but protection says `CI` (uppercase), PRs will never pass. Always match exactly.
- **gh CLI auth** — the worker's profile must have `gh` authenticated. The token-in-URL from workspace setup covers `git push`, but `gh pr create` needs separate auth. For scratch workspaces, `gh` reads from the profile's `~/.config/gh/hosts.yml`, not the env token.
- **`gh pr checks` polling** — this command polls until CI completes. It's safe to run inline (not background) because it's a single blocking call, not an inline test suite.
