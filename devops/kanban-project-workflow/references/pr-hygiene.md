# PR Hygiene — Branch Reuse & Merge Verification

## Pitfall: Reviewer marks task done but PR never merged

After approving a PR, the reviewer must verify that auto-merge will actually proceed before marking the task `done`. Check the PR's merge state:

```bash
gh pr view <N> --repo <repo> --json mergeStateStatus,mergeable
```

| mergeStateStatus | Meaning | Action |
|---|---|---|
| `CLEAN` | Ready to merge | ✅ Auto-merge will proceed. Task can be marked done. |
| `CONFLICTING` / `DIRTY` | Merge conflict | ❌ Needs rebase. Do NOT mark done. |
| `BEHIND` | Main moved forward | ❌ Needs rebase. Do NOT mark done. |
| `BLOCKED` | CI running | ⏳ Wait for CI. Check again after CI completes. |

**Concrete case**: PR #105 (music-library) was approved by reviewer, task t_34de5101 marked done, but PR stayed CONFLICTING for hours. The auto-merge could never proceed — it needed a manual rebase. The reviewer should have caught `mergeStateStatus: DIRTY` and either rebased or reported it.

## Pitfall: Workers create new branches/PRs instead of force-pushing

When fixing review feedback or rebasing an existing PR, always push to the **same branch** so the PR updates. Do NOT create a new branch with a truncated name and a new PR.

| ❌ Bad pattern | ✅ Correct |
|---|---|
| `feat/t_3b1ff5` → PR #168 (same ticket as #151) | `feat/t_3b1ff519` → force-push → PR #151 updates |
| `feat/t_8e211c` → PR #160 → `feat/t_8e211c-v3` → PR #166 | All changes on `feat/t_8e211ca6` → PR #151 updates |

**Why this matters:**
- Stale PRs accumulate (#151, #160 left open when #166 was the real one)
- Branch names get truncated and inconsistent (`feat/t_3b1ff5` vs `feat/t_3b1ff519`)
- Manual cleanup needed: close stale PRs, delete orphan branches
- Reviewers don't know which PR is authoritative

**The rule**: same ticket = same branch = same PR. After rebase or fix, `git push --force-with-lease origin <branch>`. Only create a new PR if the original was already merged and the fix is a separate changeset.
