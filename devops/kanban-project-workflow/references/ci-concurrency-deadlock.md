# CI Concurrency Deadlock — GitHub Actions

## Symptom

PR checks show "waiting for status to be reported" indefinitely. A CI run exists (`gh run list` shows it "pending" or "queued") but never starts executing jobs. `gh pr checks` reports "no checks reported."

## Root Cause

The `concurrency` group with `cancel-in-progress: true` creates a deadlock when:

1. Push commit A triggers CI run A (starts executing, has a typecheck failure)
2. Push commit B (fix) creates CI run B → cancels run A due to `cancel-in-progress`
3. Run B enters "pending" state but gets stuck before any jobs execute
4. When run B is manually cancelled, the concurrency group releases → run A resumes
5. Run A now runs to completion with the OLD (broken) code

The concurrency group name `${{ github.workflow }}-${{ github.ref }}` means runs on the same branch share a group. `cancel-in-progress` cancels the old run when a new one starts, but if the new run gets stuck in "pending" before any job executes, there's no run to cancel — and the deadlocked state persists.

## Detection

```bash
# Check if a run is stuck in pending/queued with no jobs
gh run list --repo Seven74AI/music-library --branch <branch> --limit 3
# Look for "pending" or "queued" status

gh run view <run_id> --repo Seven74AI/music-library --json status,jobs
# If status is "queued" but jobs array is empty → stuck
```

## Fix

Push an empty commit to force a fresh CI run. The new push creates a new run with the same concurrency group, cancelling whatever was stuck:

```bash
git commit --allow-empty -m "chore: trigger CI"
git push origin <branch>
```

The empty commit is a no-op — it just forces Git to create a new SHA so GitHub Actions treats it as a new push event.

## Prevention

Avoid rapid push sequences on the same branch. Let CI complete before pushing fixes. If CI already failed and you need to push a fix, ensure the fix push is rapid so the concurrency group handles it cleanly (old run cancelled before jobs start, new run picks up immediately).
