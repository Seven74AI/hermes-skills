# Review Suggestion Audit — PRs + Kanban → GitHub Issue

Collect all non-blocking reviewer suggestions from both GitHub PRs and kanban
tickets, compile into a single tracking GitHub issue. Useful for periodic
project health checks or post-milestone reviews.

## When to Use

- User asks "collect all reviewer suggestions from the last N weeks"
- Post-audit: after a wave of PRs, surface polish debt before it accumulates
- Pre-release: sweep for cosmetic issues that reviewers flagged but didn't block on
- Any time the user wants a consolidated view of non-blocking feedback

## Overview

Two data sources, one output:
1. **GitHub PRs** — reviews (APPROVED/CHANGES_REQUESTED/COMMENTED) + inline review comments
2. **Kanban tickets** — reviewer task_runs summaries + task_comments from reviewer

Filter both for actual suggestions (not "LGTM" / "APPROVED" boilerplate), compile
into a well-structured GitHub issue.

## Step 1: Fetch PR Review Suggestions

Query the GitHub API for PRs updated in the time window. For each PR, fetch
reviews and review comments.

```python
import urllib.request, json, time

two_weeks_ago = int(time.time()) - 14 * 86400
token = "..."  # from ~/.hermes/.env or gh auth token

def gh_api(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "hermes-agent")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

# Get all PRs updated in window
all_prs = []
page = 1
while True:
    result = gh_api(f"/repos/{owner}/{repo}/pulls?state=all&sort=updated&direction=desc&per_page=100&page={page}")
    if not result: break
    filtered = [pr for pr in result if pr['updated_at'] >= cutoff_iso]
    all_prs.extend(filtered)
    if len(filtered) < len(result): break
    page += 1

# For each PR, get reviews + review comments
for pr in all_prs:
    reviews = gh_api(f"/repos/{owner}/{repo}/pulls/{pr['number']}/reviews")
    comments = gh_api(f"/repos/{owner}/{repo}/pulls/{pr['number']}/comments")
    # Extract actionable suggestions (see filtering below)
```

## Step 2: Fetch Kanban Reviewer Feedback

Query kanban.db for reviewer task_runs and reviewer-authored comments on
recent tasks.

```python
import sqlite3

db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')

# Reviewer run summaries from last 2 weeks
cursor = db.execute("""
    SELECT tr.id, tr.task_id, tr.summary, tr.started_at, t.title
    FROM task_runs tr
    JOIN tasks t ON t.id = tr.task_id
    WHERE tr.profile = 'reviewer' AND tr.started_at >= ?
    ORDER BY tr.started_at DESC
""", (two_weeks_ago,))

# Reviewer comments on recent tasks
cursor = db.execute("""
    SELECT tc.id, tc.task_id, tc.body, tc.created_at
    FROM task_comments tc
    JOIN tasks t ON t.id = tc.task_id
    WHERE tc.author = 'reviewer'
    AND (t.created_at >= ? OR t.started_at >= ?)
""", (two_weeks_ago, two_weeks_ago))
```

## Step 3: Filter for Actual Suggestions

Not all review text is a suggestion. Filter with regex patterns that indicate
actionable feedback:

```python
SUGGESTION_PATTERNS = [
    r'\bsuggestion\b', r'\bcould\b', r'\bshould\b', r'\bconsider\b',
    r'\bnit\b', r'\boptional\b', r'\brecommend\b', r'\bbetter to\b',
    r'\bmight\b', r'\bnon-blocking\b', r'\bprefer\b', r'\bideally\b',
    r'\bwould be nice\b', r'\bnot required\b', r'\bfollow-up\b',
    r'\bperhaps\b', r'\bpossible improvement\b',
    r'\bnote:\b', r'\bworth\b', r'\binstead\b', r'\brather\b',
]

def has_suggestion(body):
    body_lower = body.lower()
    return any(re.search(pat, body_lower) for pat in SUGGESTION_PATTERNS)

def extract_suggestions(body):
    """Extract individual suggestion lines from a review body."""
    suggestions = []
    for line in body.split('\n'):
        line_lower = line.strip().lower()
        if not line.strip(): continue
        for pat in SUGGESTION_PATTERNS:
            if re.search(pat, line_lower):
                clean = line.strip()
                clean = re.sub(r'^[-*]\s+', '', clean)     # strip bullets
                clean = re.sub(r'^\d+\.\s+', '', clean)     # strip numbered lists
                suggestions.append(clean)
                break
    return suggestions
```

This filters out:
- Pure APPROVED/LGTM reviews with no actionable feedback
- Boilerplate "Reviewed by Hermes Agent"
- CI verification results (those are facts, not suggestions)

## Step 4: Create GitHub Issues

Compile suggestions into markdown issue bodies. One issue for PR suggestions,
one for kanban suggestions (or merge if small enough).

```bash
gh issue create \
  --repo <owner>/<repo> \
  --title "Reviewer Suggestions from PRs — Last 2 Weeks (<date range>)" \
  --body-file /tmp/issue_body.md
```

Issue body template:
```markdown
## PR #N — <title>
**Reviewer:** <name> | **Verdict:** <state> | <date>
[PR Link](url)

- suggestion 1
- suggestion 2

---
```

## Common Suggestions Found (the-swarm, May 2026)

Recurring patterns from a real audit:

| Category | Suggestion | Frequency |
|----------|-----------|-----------|
| CSS | Redundant `[data-tooltip]:hover::after` rule | 3 PRs |
| Security | `innerHTML` instead of `textContent` for static content | 2 files |
| DRY | `PHASE_NUMBER` duplicated in PrestigeSystem + PrestigePanel | 2 files |
| Dead code | `formatNumber` imported but unused | 1 file |
| Dead tests | `it('marks onboarding as complete')` always skipped | 2 PRs |
| Types | E2E helpers use `page: any` instead of `Page` | 1 PR |
| Wiring | `migrateSave` not called from `SaveManager.load()` | pre-existing |
| Naming | `foodConsumedPerSec` vs `foodProducedPerSec` inconsistency | 1 PR |

## Pitfalls

- **PR reviews from the PR author don't count** — only reviews by other users
- **Review comments (inline) vs reviews (top-level)** — fetch both endpoints
- **Kanban runs are per-attempt** — the same task may have 5+ reviewer runs;
  dedup in the issue by grouping under the task_id
- **GitHub issue body limit is 65K chars** — for very large audits, split
  into multiple issues or summarize recurring patterns upfront
- **Archived tasks still count** — if they were active in the time window,
  their reviewer feedback is valid
