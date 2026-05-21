# Extract Clean Diff from Polluted Branch

When a feature branch has accumulated unrelated commits (consolidation,
dep bumps, cleanup sweeps) that were never merged to upstream main,
extract only the feature's diff and create a clean commit.

## Symptoms

- PR shows 10+ commits but only 3-4 are the actual feature
- `gh api repos/X/compare/main...<branch>` shows "diverged" for old commits
- Commits from days/weeks ago appear in the PR that aren't on main
- CI workflow regressions (|| true, wrong node version) in the diff

## Diagnosis

```bash
# List ALL commits on branch not on main
gh api repos/X/compare/main...<branch> --jq '.commits[] | {sha: .sha[:8], date: .commit.author.date[:10], message: .commit.message[:60]}'

# Find which files the feature commits touched (vs stale commits)
git diff-tree --no-commit-id --name-only -r <feature-commit-sha>
```

## Extraction

```bash
# Create fresh branch from main
git checkout main && git pull
git checkout -b feat/clean-branch

# Extract only the feature files' diff from the polluted branch
git diff main origin/<polluted-branch> -- \
  file1.ts file2.ts file3.ts ... \
  > /tmp/clean-feature.patch

# Apply cleanly
git apply --3way /tmp/clean-feature.patch

# Single clean commit
git add -A
git commit -m "feat: <description>"
git push origin feat/clean-branch

# Close old PR, create new one with label
gh pr close <old-number> --repo X --comment "Replaced by #<new>"
gh pr create --repo X --base main --head feat/clean-branch \
  --label "kanban:$TASK_ID" --title "..." --body "..."
```

## Real Case — Shop PR #109 (2026-05-20)

Branch `feat/t_bbce3b` had 9 commits not on main:
- 4 legit (French translations by worker t_bbce3b35)
- 5 stale (consolidation PR #99, cleanup sweep #100, dep bumps from May 18-19)

Commit `0774571` (consolidation) re-introduced `|| true` in the CI typecheck
step — a regression from a fix applied 12 hours earlier. The stale commits
were never on upstream main because the consolidation PR was merged to the
fork but the upstream PR was closed without merging.

Extracted only the 16 translation files → single clean commit → new PR #111.
