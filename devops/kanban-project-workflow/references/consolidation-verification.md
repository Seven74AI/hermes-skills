# Consolidation PR Verification Checklist

**When to use:** After an upstream consolidation PR merges, BEFORE telling the user
something was included in it.

## The rule

> Never claim a fix/feature was consolidated into upstream PR #X until you've
> verified the actual file list. Check, don't assume.

## Verification commands

```bash
# Check what files actually landed in the merged upstream PR
gh pr view N --repo mnlamart/<repo> --json files | jq '.files[].path'

# For PRs that were squash-merged with a single commit:
gh pr view N --repo mnlamart/<repo> --json commits | jq '.commits[].oid' | head -1
```

## Common failure mode

You created multiple fork PRs (#74 UI fixes, #77 flaky test) and one upstream
consolidation PR (#38). You assume the consolidation includes everything. But
upstream #38 was created from the fork's `main` branch which may have been
out of sync with the fork's feature branches.

**Always verify file lists before reporting to the user.**

## False-positive commits from previous squash merges

`git log upstream/main..origin/main` shows commits based on SHA, not content.
When a fork PR was squash-merged into upstream under a different SHA, it still
appears in the log. Example:

```bash
$ git log upstream/main..origin/main --oneline
120b131 fix: add clientAction (#170)   ← already merged as upstream #73!
fa13462 chore: Vite 7 prep (#171)      ← genuinely new
```

**Cross-reference before writing the PR description:**

```bash
# List all apparent fork-only commits
git log upstream/main..origin/main --oneline

# Check which fork PRs were already squash-merged upstream
gh pr list --repo mnlamart/<repo> --state merged --limit 30 \
  --json number,title --jq '.[].title'

# Remove any fork PR whose title matches an upstream PR title
```

The #170 → upstream #73 pattern is specifically: same logical change, different
SHA, because upstream squash-merged from the fork's PR but `git log` can't
deduplicate by content.

**Real case (2026-07-14):** Consolidation PR #74 listed 9 commits from
`git log upstream/main..origin/main`. But #170 was already merged as upstream
#73 — false positive. User: "I think you put too much #170 was already merged
on upstream…"

## Fork sync after upstream merge

After upstream merges, the fork gets out of sync (ahead/behind). Procedure:

```bash
cd repo
git fetch upstream
git reset --hard upstream/main
git push origin main --force
# Restore branch protection if needed
```

## Real case (2026-07-08)

- Fork PR #74 (UI fixes) → upstream #38
- Fork PR #77 (flaky test fix) → NOT in #38
- Agent claimed "both consolidated" without checking — WRONG
- Had to create separate upstream #39 for the test fix
- ⛔ User feedback: "Stop assuming shit ffs" — verify, don't narrate
