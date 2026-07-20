# Upstream Consolidation PR — Fork → Upstream Batch Sync

Use when syncing a batch of commits from the fork (`Seven74AI/<repo>`) to upstream
(`mnlamart/<repo>`) as a single consolidated PR. This is the pattern for periodic
syncs after multiple feature PRs have been merged on the fork.

## When to consolidate

- After the kanban board is clean (no running/blocked tasks)
- When there are 10+ new commits on the fork that haven't been pushed upstream
- Before starting a new work cycle (ensures upstream is in sync)

## Procedure

### 1. Verify the board is clean

```bash
hermes kanban list | grep -v "✓"
# Must return nothing — no running, blocked, or todo tasks
```

### 2. Create consolidation branch from upstream/main

```bash
git fetch upstream main
git checkout -b consolidation/sync-YYYYMMDD upstream/main
```

### 3. Merge all fork commits

```bash
git merge origin/main --no-edit
```

This should be a fast-forward merge. If there are conflicts with upstream (divergent
histories), something is wrong — check whether upstream has been force-pushed.

### 4. Count and verify the commits

```bash
git log --oneline upstream/main..origin/main | wc -l
git log --oneline upstream/main..origin/main | head -5   # spot check
```

### 5. Push to fork

```bash
git push origin consolidation/sync-YYYYMMDD
```

### 6. Create the PR (fork → upstream)

```bash
gh pr create \
  --repo mnlamart/<repo> \
  --head Seven74AI:consolidation/sync-YYYYMMDD \
  --base main \
  --title "consolidation: sync N commits from Seven74AI/<repo> fork" \
  --body-file /tmp/consolidation-body.md
```

**Always use `--body-file`** for the PR body — it contains backticks, code references,
and other characters that break shell arguments.

### 7. PR body template

```markdown
## Consolidation PR — N commits from Seven74AI/<repo>

### Category 1
- ...

### Category 2
- ...

---

Builds on previous consolidation #X (sync N commits, YYYY-MM-DD).
```

### 8. Clean up

After the PR is created, switch back to the working branch and delete the local
consolidation branch:

```bash
git checkout feat/working-branch
git branch -D consolidation/sync-YYYYMMDD
```

## Pitfalls

- **Don't sync while kanban tasks are active.** Force-pushing fork main while
  workers are on feature branches creates risk even though branches are technically
  independent. Wait for a clean board.

- **Don't create the PR from local `main`.** Always branch from `upstream/main`
  directly — local `main` may be stale after previous fork syncs.

- **Don't use `origin/main` as the PR base.** The PR's base is `upstream/main`,
  the head is `Seven74AI:consolidation/sync-YYYYMMDD` (which contains upstream/main
  + fork commits).

- **Check for existing consolidation PRs first.** If one already exists open,
  you may need to close it and create a fresh one, or rebase the existing one.

## Real case (2026-07-13)

PR #72 (mnlamart/music-library) — 50 commits, 56 files, +3316/-270, fast-forward
clean. Previous consolidation: #11 (101 commits, 2026-07-06).
