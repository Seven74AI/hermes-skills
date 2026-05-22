# Cross-Repo PR Status Check

Quick audit pattern for "where are we on all boards?" queries.
Checks PRs on forks, upstream repos, and kanban tickets in one pass.

## Why both forks AND upstream

PRs can live on either side:
- **Forks** (`Seven74AI/<repo>`) — coder PRs, cleanup sweeps, CI fixes
- **Upstream** (`mnlamart/<repo>`) — consolidation PRs, cross-fork contributions
- **Kanban boards** — tickets that reference PRs but aren't done yet

Ghost PRs on forks are a known issue (see `ghost-pr-cleanup.md`).

## Command

```bash
# PRs on all forks (all states — shows both open and recently merged/closed)
for repo in Seven74AI/shop Seven74AI/music-library Seven74AI/the-swarm; do
  echo "=== $repo ==="
  gh pr list --repo "$repo" --state all --limit 15 \
    --json number,title,state,headRefName,author,createdAt \
    --jq '.[] | "\(.state)\t#\(.number)\t\(.title)"'
  echo
done

# Upstream open PRs (cross-fork contributions)
for repo in mnlamart/shop mnlamart/music-library mnlamart/the-swarm; do
  echo "=== $repo (upstream) ==="
  gh pr list --repo "$repo" --limit 10 \
    --json number,title,state,headRefName \
    --jq '.[] | "\(.state)\t#\(.number)\t\(.title)"'
  echo
done

# Kanban tickets still open
for board in shop music-library the-swarm; do
  echo "=== $board kanban ==="
  hermes kanban --board "$board" list 2>&1 | grep -E '^\s*[⬜⚡🔴⚠]' || echo "(clean)"
  echo
done
```

## Interpreting output

| Signal | Meaning |
|--------|---------|
| All 3 boards show `(clean)` or only `✓ done` | No work in progress |
| PR on fork but no kanban ticket | Orphan PR — close or create ticket |
| Kanban ticket but no PR | Worker may be in progress or blocked |
| PR `CLOSED` on fork but ticket `done` | Normal — PR was consolidated into another |
