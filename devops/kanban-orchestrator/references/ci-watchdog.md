# CI Watchdog — Label-based GitHub CI gating for Kanban

## Problem

Workers create PRs on a fork repo (e.g. `Seven74AI/shop`). The dispatcher's
`respawn_guarded` mechanism scans task comments for GitHub PR URLs within
the last 24h (`_RESPAWN_GUARD_PR_WINDOW = 86400s`). Any PR URL — open,
merged, or closed — triggers `active_pr` guard, blocking respawn.

PR URLs in comments are **persistent**: merging/closing the PR does not
delete the comment. Tasks stay blocked for 24h.

## Solution: Labels instead of URLs

Workers apply a `kanban:TASK_ID` label to the PR and NEVER post the URL
in a comment. A CI-watchdog cron job finds PRs by label, checks CI, and
merges green PRs.

### ⛔ REQUIRED: Workflow MUST be named "CI"

The branch protection rule requires `contexts: ["CI"]`. The GitHub Actions
workflow in every repo MUST be named `CI` (not `🚀 Deploy`, not `deploy`, not
anything else). The check name in branch protection is an exact match — if
the workflow is named `🚀 Deploy`, the required check `CI` never appears and
`gh pr merge` always fails.

```yaml
# .github/workflows/deploy.yml (or ci.yml)
name: CI   # ← MUST be exactly "CI"
```

**Repos verified 2026-05-20:**
| Repo | Workflow | OK? |
|------|----------|-----|
| the-swarm | CI | ✅ |
| shop | CI (fixed from 🚀 Deploy) | ✅ |
| music-library | CI (fixed from 🚀 Deploy) | ✅ |
| baguette | CI | ✅ |
| glance | CI | ✅ |
| videogame-lab | CI | ✅ |
| edgee-lab | CI | ✅ |

### Worker flow

```bash
# 1. Push branch, create PR with label
gh pr create --repo Seven74AI/shop --base main --head feat/N \
  --label "kanban:$HERMES_KANBAN_TASK"

# 2. Block — NO PR URL in the reason
kanban_block(reason="awaiting CI: PR label kanban:$HERMES_KANBAN_TASK")
```

### CI-watchdog script

A single universal script (`~/.hermes/scripts/ci-watchdog.py`) handles ALL repos. It iterates over a `BOARD_REPOS` config dict — add a new repo with one line:

```python
BOARD_REPOS = {
    'shop':       'Seven74AI/shop',
    'the-swarm':  'Seven74AI/the-swarm',
}
```

For each board:
1. Finds open PRs with `kanban:` labels via `gh pr list`
2. Finds blocked tasks with `awaiting CI` in their block reason
3. Matches PRs to tasks via label
4. Checks CI status (`gh run list --branch <branch>`)
5. If green → merges PR (`gh pr merge --merge --delete-branch`)
6. If red → comments error on the task
7. Unblocks the task

### Deployment

```bash
hermes cron create \
  --name "CI Watchdog" \
  --schedule "every 2m" \
  --script ci-watchdog.py \
  --no-agent \
  --deliver local
```

`--no-agent` means no LLM is invoked — the script runs directly, zero tokens.
`--deliver local` means no Telegram spam, just task comments.

### Why 2-minute interval

GitHub Actions CI typically takes 3-8 minutes. Checking every 2 minutes
gives at most 2 minutes of latency between CI green and merge + unblock.

### Edge cases handled

| Case | Action |
|------|--------|
| PR but no blocked task | Skip (tasks block after push) |
| CI not started yet | Skip, check next tick |
| CI red | Comment error log, unblock for fix |
| Merge conflict | Comment conflict, unblock for manual |
| PR already merged | Unblock directly |
| Multiple PRs same task | Take the most recent (highest number) |

### Branch protection (required per repo)

Every repo covered by the CI watchdog MUST have branch protection on `main`:

```bash
gh api "/repos/$OWNER/$REPO/branches/main/protection" --method PUT --input - <<JSON
{
  "required_status_checks": {"strict": true, "contexts": ["CI"]},
  "enforce_admins": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

Without this, `gh pr merge` succeeds even when CI is red — the watchdog would merge broken code.

### Adding a new repo

Add one line to `BOARD_REPOS` in `ci-watchdog.py`, then apply branch protection:

```python
BOARD_REPOS = {
    'shop':       'Seven74AI/shop',
    'the-swarm':  'Seven74AI/the-swarm',
    'new-project': 'Seven74AI/new-project',  # ← add here
}
```

No new cron job, no new script. The existing CI Watchdog cron picks it up on the next tick.

### Silent watchdog pattern (critical for no-agent scripts)

For `--no-agent` cron jobs, **stdout is delivered verbatim**. Empty stdout = no notification. The CI watchdog script MUST follow this pattern:

```python
def main():
    any_work = False
    for board, repo in BOARD_REPOS.items():
        if process_board(board, repo):
            any_work = True
    # if any_work: nothing more to print — actions already logged
    # else: silent — no notification sent

if __name__ == '__main__':
    main()
```

**⛔ Never print headers outside the `if any_work:` block.** A `print("🔔 CI WATCHDOG")` at the top level fires on every tick — even idle ones — and the cron system delivers the message. This produces empty notifications like:

```
🔔 CI WATCHDOG

To stop or manage this job...
```

**Real case (2026-05-20):** The header was printed before `main()`, causing an empty notification every 2 minutes. Fixed by moving the header inside `process_board()`, gated behind `first` flag so it only prints when actual work starts.

### Pitfall: `gh run view` needs `databaseId`, not `url`

`gh run list --json url` returns the HTML page URL (e.g. `https://github.com/.../actions/runs/26193477898`). Passing this to `gh run view <url> --log-failed` causes a malformed API URL with double-nesting:

```
HTTP 404: https://api.github.com/repos/.../actions/runs/https://github.com/.../actions/runs/26193477898
```

**Fix:** Use `--json databaseId` instead — returns the numeric run ID that `gh run view` accepts directly.

```python
# ❌ Broken — passes HTML URL to gh run view
runs = ['gh', 'run', 'list', '--json', 'url', ...]
url = parts[2]  # "https://github.com/..."
subprocess.run(['gh', 'run', 'view', url, '--log-failed'])  # double-nested URL → HTTP 404

# ✅ Correct — passes numeric databaseId
runs = ['gh', 'run', 'list', '--json', 'databaseId', ...]
run_id = parts[2]  # "26193477898"
subprocess.run(['gh', 'run', 'view', str(run_id), '--log-failed'])  # works
```

**Real case (2026-05-20):** Shop task t_4b967237 had CI failed for 7 ticks with comment "HTTP 404: Not Found" instead of the actual Playwright failure. Root cause: `url` field was passed to `gh run view` which expects an ID.
