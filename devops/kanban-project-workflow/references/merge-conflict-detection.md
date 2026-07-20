# Merge Conflict Marker Detection

## What

Merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) in a committed diff indicate an unresolved merge that was committed by mistake. They are ALWAYS blocking — no exceptions.

## Detection (coder — pre-commit)

In `requesting-code-review` Step 1a, before any other check:

```bash
git diff --cached | grep -n '<<<<<<<\|=======\|>>>>>>>'
# or for unstaged:
git diff | grep -n '<<<<<<<\|=======\|>>>>>>>'
```

If found: fix conflicts (`git checkout --conflict=merge <file>`, resolve, `git add`), then re-run verification.

## Detection (reviewer — PR review)

Before the Standards/Spec review, grep the PR diff:

```bash
gh pr diff <number> | grep -n '<<<<<<<\|=======\|>>>>>>>'
```

If found, report "BLOCKED — merge conflict markers found in <file>:<line>. Fix and re-submit." Do NOT approve. Do NOT proceed to review.

## Real cases

### Case 1: PR merged clean, then direct push introduced markers (2026-07-13)

PR #113 (kanban task `t_2f15554c`, reviewer `t_55ba4d83`) merged cleanly — the PR diff (`gh pr diff 113`) showed only `+.eslintcache` in `.gitignore`, no conflict markers. The reviewer did their job correctly.

The conflict markers were introduced AFTER the merge by commit `f9ed03d` ("chore: remove prisma/test.db from tracking, add to .gitignore"), a direct push to main with no PR. The worker had a dirty working tree from an unresolved merge and committed `<<<<<<< HEAD` / `=======` / `prisma/test.db` into `.gitignore` without review.

**Root cause**: worker pushed directly to main bypassing the PR workflow entirely. The merge conflict was trivially visible to any reviewer — it passed because there was no review at all. Fixed by `bae1d31`.

**Forensic technique**: to trace how a bug passed review, compare what the reviewer saw (`gh pr diff <N>`) against the actual file timeline (`git log --all --oneline -- <file>`). The discrepancy reveals whether the bug was in the PR (reviewer failure) or introduced after merge (process failure).

### Case 2: Unresolved merge in PR diff (hypothetical)

If a PR diff itself contains conflict markers, the reviewer MUST catch them with the grep check below. This has not yet occurred in practice — all detected marker incidents have been post-merge direct pushes.
