# CI Debugging — Quick patterns

## Check if a failure is pre-existing

Before fixing a CI failure, verify it wasn't already failing before your changes:

```bash
# Get the current run ID
gh run list --repo Seven74AI/music-library --branch <branch> --limit 1 --json databaseId

# Get the previous run (before your push) and compare failures
gh run view <prev_run_id> --json conclusion,jobs --jq '.jobs[] | select(.conclusion=="failure") | .name'

# Check full failure details
gh run view <prev_run_id> --job <job_id> --log 2>&1 | grep "failed$"
```

**When a test shows up in both the previous run AND your current run, it's pre-existing — don't chase it.**

Real case: `player-queue.test.ts:636` "now-playing sheet" failure appeared in 3 consecutive CI runs across multiple commits. It was a test isolation issue (prior test leaving a Radix dialog open), not a regression from the PR changes. Fixed separately with `page.keyboard.press("Escape")` cleanup.

## GitHub CLI — run vs job queries

```bash
# Run-level: list recent runs
gh run list --repo Seven74AI/music-library --branch <branch> --limit 3 --json status,conclusion,databaseId,headSha

# Run-level: view a specific run's job conclusions  
gh run view <run_id> --json conclusion,jobs --jq '.jobs[] | select(.conclusion=="failure") | {name, conclusion}'

# Job-level: get logs for a specific failed job
gh run view <run_id> --job $(gh run view <run_id> --json jobs --jq '.jobs[] | select(.name=="playwright (1)") | .databaseId') --log

# Note: gh run list doesn't support --json jobs on the list command — use gh run view for jobs

## Concurrency cancels runs on force push

The `deploy.yml` workflow has `concurrency: cancel-in-progress: true`:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

**Pitfall:** Every `git push --force` while a CI run is in progress cancels the previous run. Multiple rapid force pushes leave no clean run. This manifests as all jobs showing "cancelled" and the run marked "failure."

**Rule:** After force-pushing, wait for CI to complete before pushing again. If you need to amend, wait for the current run to finish first. If runs keep getting cancelled, squash to one commit and push once.

**Symptom check:** All jobs show `completed/cancelled` → you force-pushed during a run.

```bash
gh run list --repo Seven74AI/music-library --branch <branch> --limit 5 \
  --json status,databaseId,headSha,conclusion \
  --jq '.[] | "\(.databaseId) \(.status)/\(.conclusion) \(.headSha[0:7])"'
```
```
