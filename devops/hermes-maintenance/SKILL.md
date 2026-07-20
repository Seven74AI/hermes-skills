---
name: hermes-maintenance
description: Update, install, and maintain the Hermes Agent installation — fork-based editable installs, dependency management, and version troubleshooting.
---

Maintenance procedures for a Hermes Agent installation. Covers updating (including fork-based setups), dependency management, and install troubleshooting.

## Trigger

Use when updating Hermes, checking for new versions, troubleshooting install/import errors, or when `hermes update` returns "Already up to date!" but you know a newer version exists.

## Checking current version

```bash
hermes --version
```

Also check the git state for editable installs:
```bash
cd /usr/local/lib/hermes-agent
git describe --tags
git log --oneline -1
```

## Updating from a fork (editable install)

### The problem

`hermes update` only checks **origin** (your fork), not **upstream** (NousResearch). If your fork is behind upstream, `hermes update` will report "Already up to date!" even when major new releases exist.

### The fix

```bash
cd /usr/local/lib/hermes-agent

# 1. Fetch upstream tags and main
git fetch upstream main --tags

# 2. Check how far behind you are
git log --oneline HEAD..upstream/main | wc -l

# 3a. Attempt merge (may fail with massive conflicts if fork diverged)
git merge upstream/main --no-edit

# 3b. If merge produces 500+ conflicts (fork heavily diverged):
#     Abort and hard-reset to upstream
git merge --abort
git reset --hard upstream/main

# 4. Reinstall to pick up new dependencies
source venv/bin/activate
pip install -e .
```

### When to hard-reset vs merge

- **Hard reset** (`git reset --hard upstream/main`): Use when the fork has cherry-picked commits that are already in upstream, producing massive add/add conflicts. Most fork commits with upstream PR numbers in their messages are already absorbed.
- **Merge**: Use when the fork has genuine custom patches that aren't in upstream. Expect to resolve individual conflicts manually.

### After reset: re-apply local patches

If the fork had local-only changes (check with `git stash list` before reset):
```bash
git stash pop   # may produce conflicts — resolve individually
```

If the stash has old inline code that upstream already refactored (e.g., kanban watchers extracted to a mixin), prefer upstream's version:
```bash
git checkout --theirs <file> && git add <file> && git stash drop
```

## Checking for new releases

Search GitHub releases page:
```
site:github.com/NousResearch/hermes-agent releases latest
```

Or check tags:
```bash
git tag --sort=-v:refname | head -10
```

## Dependency management

After updating, `pip install -e .` handles new dependencies. Watch for:
- **Version conflicts**: Non-critical if from unrelated packages (e.g., mega-py wanting older tenacity)
- **New packages**: `pip install -e .` will download and install them automatically

## Pitfalls

- **`hermes update` is fork-only**: It checks `origin` (your fork), not `upstream` (NousResearch). If your fork hasn't synced with upstream, you're stuck on the old version until you manually fetch and reset/merge. The "Already up to date!" message is misleading in this context — it means your fork is up to date, not that Hermes itself is on the latest version.
- **Hard reset loses fork history**: `git reset --hard upstream/main` discards all local commits. Before doing this, verify that local commits are either cherry-picks already in upstream (look for upstream PR numbers like `(#30858)`) or are safely stashed.
- **Editable installs need explicit reinstall**: After pulling new code, `pip install -e .` is required to pick up new dependency declarations. Skipping this step means the old dependency set is used, which can cause import errors for new features.
- **Stash conflicts on refactored code**: If you stashed changes to a file that upstream heavily refactored (e.g., extracted to a mixin), the stash will conflict. Prefer upstream's version — the refactoring is intentional and your old patch is likely obsolete.
