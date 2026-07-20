# `gh` CLI Fork Pitfalls

## `gh pr list` / `gh pr view` without `--repo` defaults to upstream

When working on a fork (e.g., `Seven74AI/music-library`), `gh` CLI commands
default to the repo tracked by the `upstream` remote (`mnlamart/music-library`).
This silently queries the WRONG repo — `gh pr list` returns upstream PRs, not
fork PRs. `gh pr view 89` returns "no such PR" even when PR #89 exists on the
fork.

**Always specify `--repo` explicitly:**

```bash
# ✅ Correct
gh pr list --repo Seven74AI/music-library
gh pr view 89 --repo Seven74AI/music-library
gh run list --repo Seven74AI/music-library

# ❌ Silently queries upstream
gh pr list  # → mnlamart/music-library
gh pr view 89  # → "Could not resolve to a PullRequest"
```

**Real case (music-library 2026-07-09):** Agent reported "no open PRs on our
fork" because `gh pr list` defaulted to upstream. PR #89 was open and passing
CI on the fork the entire time. The user responded "Wtf you mean no open pr #89
on our fork?"

## `gh pr create` for a consolidation PR must target the upstream repo

When creating a consolidation PR from fork → upstream, `--repo` must point to
the **upstream** repo, and `--head` must be the fork org:

```bash
# ✅ Correct: fork → upstream
gh pr create \
  --repo mnlamart/music-library \
  --head Seven74AI:main \
  --base main

# ❌ Wrong: creates PR on fork against itself
gh pr create \
  --repo Seven74AI/music-library \
  --head main \
  --base main
```
