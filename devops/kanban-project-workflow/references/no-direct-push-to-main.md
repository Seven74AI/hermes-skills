# ⛔ No Direct Push to Main — Everything Goes Through PRs

## Rule

Workers MUST NOT push commits directly to `main` (or any protected branch). Every code change goes through a PR. Even a one-line `.gitignore` edit.

## Why

A direct push to main bypasses review entirely. The most trivial bugs (conflict markers, typos, syntax errors) become invisible — there's no reviewer, no CI gate on the commit itself, no diff for anyone to check.

## Real case (2026-07-13)

Commit `f9ed03d` ("chore: remove prisma/test.db from tracking, add to .gitignore") was pushed directly to `origin/main` on `Seven74AI/music-library` by a kanban worker with no PR. The commit introduced `<<<<<<< HEAD` / `=======` conflict markers in `.gitignore`. Fixed post-hoc by `bae1d31`.

The worker had a dirty working tree from an unresolved merge: `git merge` left conflict markers, and the worker committed the file as-is without noticing. Any reviewer would have caught this instantly — it passed because there was no review.

### Forensic trace

```bash
# 1. The PR diff was clean — reviewer did nothing wrong
gh pr diff 113  # only +.eslintcache, no conflict markers

# 2. The culprit was a post-merge direct push
git log --all --oneline -- .gitignore | head -5
# f9ed03d chore: remove prisma/test.db from tracking, add to .gitignore
# 0b04c41 feat: P3 cleanup — stop handler (#113)   ← merge was clean

# 3. The commit has no PR number — direct push, not a merge commit
git show f9ed03d -- .gitignore
# +<<<<<<< HEAD
#  .eslintcache
# +=======
# +prisma/test.db
```

## Detection

When investigating how a bug passed review:

1. Check what the reviewer actually saw: `gh pr diff <N>`
2. Check the file's commit timeline: `git log --all --oneline -- <file>`
3. If the bug appears in a commit with no PR number → direct push, review was bypassed
4. If the bug appears in a merge commit → reviewer missed it in the PR diff

## Prevention

1. **Branch protection on `main` with `enforce_admins: true`.** The default GitHub branch protection (`required_pull_request_reviews: 1`) can be bypassed by admins unless `enforce_admins` is explicitly enabled. Check with:
   ```bash
   gh api repos/<owner>/<repo>/branches/main/protection | jq '.enforce_admins.enabled'
   ```
   If `false`, admins (including bot tokens with admin scope) can push directly to main without a PR. Fix:
   ```bash
   gh api repos/<owner>/<repo>/branches/main/protection --method PUT \
     --input <(gh api repos/<owner>/<repo>/branches/main/protection | \
       jq '. + {enforce_admins: {enabled: true}}')
   ```
   Real case (2026-07-13): `Seven74AI/music-library` had branch protection with 1 review required, but `enforce_admins: false` — the `Hermes Coder` token with admin rights pushed `f9ed03d` directly to main without review. Enabling `enforce_admins` closed the gap.

2. **Pre-commit hook:** `grep -n '<<<<<<<\\|=======\\|>>>>>>>'` in staged files (see `merge-conflict-detection.md`)

3. **Worker rule:** `git push` only to feature branches on the fork, never to upstream main
