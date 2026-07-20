# GitHub Operations

All issue and PR operations on the fork must pass `--repo Seven74AI/music-library` explicitly. The local clone resolves `gh` to upstream by default.

## Issue creation

```bash
gh issue create \
  --repo Seven74AI/music-library \
  --title "..." \
  --body "..." \
  --label "ready-for-agent"
```

## Issue labels

```bash
gh issue edit <number> --repo Seven74AI/music-library --add-label "ready-for-agent"
```

## Issue list

```bash
gh issue list --repo Seven74AI/music-library --state open --label ready-for-agent
```

## PR creation

```bash
gh pr create \
  --repo Seven74AI/music-library \
  --base main \
  --title "..." \
  --body "..."
```

## Consolidation PR to upstream (cross-repo)

When the token doesn't have write access to the upstream fork (`mnlamart/music-library`), use a cross-repo PR. The head branch lives on `Seven74AI/music-library`:

```bash
gh pr create \
  -R mnlamart/music-library \
  --base main \
  --head Seven74AI:main \
  --title "Consolidation: sync from Seven74AI fork" \
  --body "Sync from Seven74AI/music-library main."
```

Auto-merge requires write access to the target repo — consolidation PRs need manual merge by upstream maintainers.
