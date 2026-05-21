# Pre-Spawn Health Watchdog

Scans all boards for `ready` tasks with issues that would cause dispatch failure
or silent waste. **Notification only** — does not modify anything. Silent when clean.

Runs every 5 minutes via `--no-agent` cron (`pre-spawn-watchdog.py`).

## Checks performed

| Check | Why it matters |
|-------|---------------|
| **NO-SKILLS** | Worker spawns without skill → crash on first tool call |
| **NO-MRT** (max_runtime_seconds) | Falls back to ~120s → timeout loop on any non-trivial task |
| **PR-URL-IN-BODY** | Triggers `respawn_guarded` → task blocked for 24h |
| **PR-URL-COMMENTS** | Same as above, but in comment history |
| **NO-ASSIGNEE** | `ready` task will never be picked up by dispatcher |

## False positive rules (built into the script)

### RECETTE merge targets
Tasks whose title starts with `RECETTE:` are organizational merge targets, not
executable work. They're intentionally unassigned. **Skipped.**

### Reviewer tasks (NO-SKILLS / NO-MRT)
Reviewer tasks created by the block watchdog often have NULL skills and
max_runtime_seconds. The dispatcher injects profile defaults for these —
they don't cause spawn failure. **Not skipped by the script, but should be
considered low-priority noise.** If flagged, verify the reviewer profile
has default skills configured before acting.

## PR URL detection — exact regex, not LIKE

The dispatcher's `_RESPAWN_GUARD_PR_URL_RE` uses:
```python
re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+", re.IGNORECASE)
```

The watchdog script MUST use the same regex for accuracy. Using SQL
`LIKE '%github.com%pull%'` produces false positives when comments contain
GitHub Actions run URLs with query parameters like `?exclude_pull_requests=true`.

**Real case (2026-05-20):** Shop t_4b967237 was flagged 7 times for
PR-URL-COMMENTS. All matches were CI watchdog comments containing actions
run URLs (not PR URLs). The SQL `LIKE '%pull%'` matched the query string
fragment `exclude_pull_requests`.

**Fix:** The script now uses the dispatcher's exact regex in Python, and
the SQL comment scan matches on `%github.com%pull%` as a pre-filter, then
validates with the regex. False positives from actions run URLs are eliminated.

## Deployment

```bash
hermes cron create \
  --name "Pre-Spawn Health Watchdog" \
  --schedule "every 5m" \
  --script pre-spawn-watchdog.py \
  --no-agent \
  --deliver origin
```

## Cron config

- `--no-agent`: script runs directly, zero tokens
- `--deliver origin`: notification only when issues found (silent when clean)
- Every 5 minutes — same cadence as block watchdog

## Adding a new check

The script structure is a simple loop over boards → tasks → checks:

```python
for t in tasks:
    problems = []
    if not t['skills']: problems.append("NO-SKILLS")
    if not t['max_runtime_seconds']: problems.append("NO-MRT")
    # ... add new checks here
    if problems:
        issues.append(...)
```

New checks should be **actionable** — flagging something the operator can fix
in <30 seconds. Don't flag informational conditions that don't block dispatch.
