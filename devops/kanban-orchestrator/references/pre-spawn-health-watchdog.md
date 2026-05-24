# Pre-Spawn Health Watchdog

Scans all boards for tasks with issues that block dispatch or waste worker slots.
**Notification only** — does not modify anything. Silent when clean.

Runs every 5 minutes via `--no-agent` cron (`pre-spawn-watchdog.py`).

## Checks performed (current)

| Check | Why it matters | State |
|-------|---------------|-------|
| **NO-ASSIGNEE** (`ready` + `blocked`) | Dispatcher ignores unassigned tasks; blocked tasks can't be unblocked manually without one | ✅ active |
| **NO-MRT** | Retired 2026-05-23 — heartbeat-first with 3600s safety net. NULL is not critical | ❌ retired |
| **PR-URL-COMMENTS(N)** | `respawn_guarded` blocks respawn for 24h when PR URLs in comments | ✅ active |
| **PR-URL-IN-BODY** | Same as above, but in body text (less common) | ✅ active |
| **STUCK-SCHEDULED** | Parent `done` but child stays `scheduled` — `skills` and `max_runtime_seconds` are often NULL on these | 🆕 May 2026 |
| **BODY-IS-NULL** | Task created without body — worker has no instructions | 🆕 May 2026 |

## Checks retired (May 2026)

| Check | Why removed |
|-------|------------|
| **NO-SKILLS** | Dispatcher injects profile skills at spawn. NULL skills in task column does not cause failure — pure noise. |

## Exclusions (intentional skips)

| Pattern | Why excluded |
|---------|-------------|
| `title LIKE 'RECETTE:%'` | Merge-target tasks — never dispatched, no assignee by design |

## New checks rationale

### STUCK-SCHEDULED

Recurring pattern: parent task completes (`done`), but child stays `scheduled` forever.
The dispatcher's promotion logic (`dispatch --dry-run` shows `Promoted=0`) misses these.
Root cause: `skills` and `max_runtime_seconds` are often NULL on the child.

**Detection query:**
```sql
SELECT c.id, c.title, c.skills, c.max_runtime_seconds, p.id as parent_id, p.status
FROM tasks c
JOIN task_links l ON l.child_id = c.id
JOIN tasks p ON p.id = l.parent_id
WHERE c.status = 'scheduled' AND p.status = 'done'
```

**Fix:** `UPDATE tasks SET status='ready', skills=<profile_default>, max_runtime_seconds=3600 WHERE id='t_xxx'`

### BODY-IS-NULL

Tasks created via CLI without `--body` or via `kanban_create` with no body. Workers spawn with no context — they either crash or do the wrong thing.

**Detection:** `SELECT id, title FROM tasks WHERE status='ready' AND body IS NULL`

## PR URL detection — exact regex, not LIKE

The dispatcher's `_RESPAWN_GUARD_PR_URL_RE` uses:
```python
re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+", re.IGNORECASE)
```

The watchdog script MUST use the same regex. Using SQL `LIKE '%github.com%pull%'` produces false positives when comments contain GitHub Actions run URLs with query parameters like `?exclude_pull_requests=true`.

**Real case (2026-05-20):** Shop t_4b967237 was flagged 7 times for PR-URL-COMMENTS. All matches were CI watchdog comments containing actions run URLs (not PR URLs).

## Silent pattern

Like all no-agent watchdogs, the script MUST be silent when clean:

```python
if not issues:
    return  # stdout empty → no cron notification delivered
```

The header (`🔍 PRE-SPAWN HEALTH — HH:MM`) only prints when issues are found.

## Deployment

```bash
hermes cron create \
  --name "Pre-Spawn Health Watchdog" \
  --schedule "every 5m" \
  --script pre-spawn-watchdog.py \
  --no-agent \
  --deliver origin
```

## Adding a new check

The script structure is a simple loop over boards → tasks → checks:

```python
for t in tasks:
    problems = []
    if not t['assignee']: problems.append("NO-ASSIGNEE")
    if not t['body']: problems.append("NO-BODY")
    # ... add new checks here
    if problems:
        issues.append(...)
```

New checks should be **actionable** — flagging something the operator can fix in <30 seconds. Don't flag informational conditions that don't block dispatch.
