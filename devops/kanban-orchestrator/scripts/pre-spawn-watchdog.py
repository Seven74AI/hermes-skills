#!/usr/bin/env python3
"""Pre-spawn health watchdog — scans all boards for ready/scheduled/blocked tasks with issues.
NOTIFICATION ONLY — does not modify anything. Silent when clean.
Runs every 5 minutes via cron (--no-agent).
"""
import sqlite3, json, re, os, sys
from pathlib import Path
from datetime import datetime, timezone

KANBAN_BASE = Path("/root/.hermes/kanban/boards")
NOW = datetime.now(timezone.utc)

# PR URL regex (same as kanban_db.py _RESPAWN_GUARD_PR_URL_RE)
_PR_URL_RE = re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+", re.IGNORECASE)

def main():
    issues = []

    for board in sorted(d.name for d in KANBAN_BASE.iterdir()
                        if (d / 'kanban.db').exists()):
        db = KANBAN_BASE / board / 'kanban.db'
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row

        # ── Ready tasks ────────────────────────────────────────────
        tasks = conn.execute("""
            SELECT id, title, assignee, body
            FROM tasks WHERE status = 'ready'
            ORDER BY created_at
        """).fetchall()

        for t in tasks:
            tid = t['id']
            title = (t['title'] or '')[:60]

            # Skip RECETTE merge targets — never meant to be assigned/dispatched
            if title.upper().startswith('RECETTE:'):
                continue

            problems = []

            # 1. PR URL in body
            if t['body'] and _PR_URL_RE.search(t['body']):
                problems.append("PR-URL-IN-BODY")

            # 2. No assignee — dispatcher ignores
            if not t['assignee']:
                problems.append("NO-ASSIGNEE")

            # 3. Body is NULL/empty — worker has no instructions
            if not t['body'] or not t['body'].strip():
                problems.append("NO-BODY")

            # 4. PR URLs in comments (same regex as dispatcher)
            pr_comments = conn.execute("""
                SELECT body FROM task_comments WHERE task_id = ?
                ORDER BY id DESC LIMIT 20
            """, (tid,)).fetchall()
            pr_url_count = sum(1 for (body,) in pr_comments if body and _PR_URL_RE.search(body))
            if pr_url_count > 0:
                problems.append(f"PR-URL-COMMENTS({pr_url_count})")

            if problems:
                issues.append(f"{board}/{tid[:14]}  {title[:50]}")
                issues.append(f"               {' '.join(problems)}")

        # ── Stuck-scheduled tasks ──────────────────────────────────
        # Tasks stuck in 'scheduled' whose parents are all done
        stuck = conn.execute("""
            SELECT c.id, c.title
            FROM tasks c
            JOIN task_links l ON l.child_id = c.id
            JOIN tasks p ON p.id = l.parent_id
            WHERE c.status = 'scheduled'
            GROUP BY c.id
            HAVING COUNT(*) = SUM(CASE WHEN p.status = 'done' THEN 1 ELSE 0 END)
        """).fetchall()

        for t in stuck:
            tid = t['id']
            title = (t['title'] or '')[:60]
            issues.append(f"{board}/{tid[:14]}  {title[:50]}")
            issues.append(f"               STUCK-SCHEDULED")

        # ── Blocked tasks with no assignee ─────────────────────────
        blocked = conn.execute("""
            SELECT id, title
            FROM tasks WHERE status = 'blocked' AND (assignee IS NULL OR assignee = '')
            ORDER BY created_at
        """).fetchall()

        for t in blocked:
            tid = t['id']
            title = (t['title'] or '')[:60]
            # Skip RECETTE here too
            if title.upper().startswith('RECETTE:'):
                continue
            issues.append(f"{board}/{tid[:14]}  {title[:50]}")
            issues.append(f"               NO-ASSIGNEE-BLOCKED")

        conn.close()

    if not issues:
        return  # silent — nothing wrong

    # Build report
    print(f"🔍 PRE-SPAWN HEALTH — {NOW.strftime('%H:%M')}")
    print(f"   {len([l for l in issues if not l.startswith(' ')])} tasks with issues")
    print()
    for line in issues:
        print(line)

if __name__ == '__main__':
    main()
