# Backup Failure — May 22-23, 2026

Real-world example of backup cron debugging and the state-snapshot explosion pattern.

## Timeline

| Date | Time | Event |
|------|------|-------|
| May 22 | 04:00 | Full backup OK (490 MB), PR #1 merged. Disk 100% full — git checkout failed. |
| May 22 | 09:00 | Night recap noted: disk 95%, state-snapshots at 5 GB, backup unstable. |
| May 23 | 04:00 | Cron marked "error" — 0 agent messages. Agent crashed before processing. |
| May 23 | 09:25 | Retry: foreground timeout at 300s, background retry reached 994 MB before session killed. |
| May 23 | ~13:00 | Disk watchdogs cleaned up. State-snapshots down to 676 MB. Quick backup OK (136 MB). |

## Root causes

1. **State-snapshots bloat**: Accumulated to 5 GB, making `hermes backup` include all of them → file grew from normal 130 MB to 994 MB
2. **PR-per-backup + LFS**: Each full backup was a dated file in git history via PR. No rotation. LFS storage growing unbounded.
3. **Foreground timeout**: Default 300s was too short for 1 GB backup
4. **04:00 crash**: Agent infrastructure failure (no messages produced) — transient, not a backup bug

## Session search debugging path

```python
# Step 1: Find cron session
session_search(query="backup PR", limit=5)
# → Found cron_8628d151e230_20260523_040006 (the 04:00 error)
# → Found cron_8628d151e230_20260523_092557 (the 09:25 retry)

# Step 2: Scroll into the retry session
session_search(
    session_id="cron_8628d151e230_20260523_092557",
    around_message_id=31097,  # the prompt message
    window=10
)
# → Saw: foreground timeout 300s → background retry → file 994 MB → process killed

# Step 3: The 04:00 session had 0 assistant messages — pure crash
session_search(
    session_id="cron_8628d151e230_20260523_040006",
    around_message_id=30759,
    window=10
)
# → Only 1 message (the user/prompt). Agent never responded.
```

## GitHub LFS check

```bash
# Repo size in KB (bare, without LFS)
gh api repos/Seven74AI/hermes-backup --jq '.size'
# → 11212 KB = ~11 MB

# Git tree shows LFS pointers (134 bytes each), not real files
gh api repos/Seven74AI/hermes-backup/git/trees/main?recursive=1 --jq '.tree[] | select(.type=="blob") | "\(.size)\t\(.path)"'
# → 134 bytes per .zip = LFS pointer
```
