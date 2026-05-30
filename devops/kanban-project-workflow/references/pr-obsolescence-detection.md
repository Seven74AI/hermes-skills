# PR Obsolescence Detection

When open PRs have merge conflicts, don't just resolve them — first check if the PR is still **legitimate** (its changes aren't already in main via a different path).

## Why this happens

- Slices/features implemented in parallel, later numbered slices merged first
- Squash-merged consolidation PRs that included equivalent work
- Refactors that touched the same files through a different branch
- Stale branches created before a major merge that already covered the feature

## Detection procedure

### 1. Check if the branch still exists

```bash
git fetch origin <branch1> <branch2>
```

### 2. Compare branch base vs main HEAD

```bash
# How far behind is the branch?
git log origin/main --oneline -5
git log origin/<branch> --oneline -3
```

### 3. List files touched by the PR

```bash
git diff $(git merge-base origin/main origin/<branch>)..origin/<branch> --stat
```

### 4. Check if equivalent files already exist in main

```bash
# All files matching the PR's topic in main
git ls-tree -r --name-only origin/main | grep <topic>
```

### 5. Diff branch files against main equivalents

```bash
# For each file the PR touches that also exists in main:
diff <(git show origin/<branch>:path/to/file) <(git show origin/main:path/to/file) | head -60
```

## Decision rubric

| Branch file vs main | Verdict |
|---------------------|---------|
| File doesn't exist in main | PR adds something new → **legitimate** |
| File exists, branch version is **older/simpler** (main has MORE code) | PR is an **earlier version** of already-merged work → **OBSOLETE** |
| File exists, branch version is different but not clearly superset/subset | Check commit dates and PR descriptions — probably **parallel implementation** → **OBSOLETE** |
| File exists, branch version has unique additions not in main | PR adds net new value → **legitimate but needs rebase** |

## Real case: the-swarm PRs #48 and #49 (2026-05-29)

PR #48 (Prestige Slice 1) and PR #49 (Prestige Slice 3) were based on a May 24 commit. By May 29, Slices 4 and 5 had been merged to main, which already included the same functionality:

- **PR #48** added flat prestige fields — main already had `prestige` object + `prestigeTree`
- **PR #49** added PrestigeTreePanel — main already had identical file with MORE features (bonus system)

Both were obsolete. Closed + deleted branches.

## Cleanup

```bash
gh pr close <N> --repo <owner/repo> \
  --comment "Closed: obsolete — <reason>"
gh api -X DELETE repos/<owner/repo>/git/refs/heads/<branch>
```
