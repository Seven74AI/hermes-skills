#!/usr/bin/env python3
"""
Cross-board kanban audit — scan ALL boards for common systemic issues.
Run this after fixing a pattern on one board to catch it everywhere.

Checks:
  1. Review tasks stuck in 'todo' (not 'ready') — dispatcher only picks 'ready'
  2. Running tasks with no heartbeat (silent workers — old SOUL.md)
  3. Tasks assigned to ghost profiles (deleted profiles, never dispatch)
  4. Tasks in 'todo' that should be 'ready' (blocking dispatch)

Usage: python3 audit-all-boards.py
  --fix    Apply fixes automatically (promote todo→ready, kill silent workers)
  --json   Output JSON for scripting
"""
import sqlite3, os, sys, time, json

BOARDS_DIR = '/root/.hermes/kanban/boards'
VALID_PROFILES = ['coder', 'reviewer', 'researcher', 'planner']

def audit_board(db_path, board_name, fix=False):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    issues = []
    
    # 1. Review tasks stuck in todo
    c.execute("SELECT id, title, assignee FROM tasks WHERE status='todo' AND title LIKE '%Review%'")
    for r in c.fetchall():
        issues.append({'board': board_name, 'type': 'review-todo', 'id': r[0], 'detail': r[1][:80]})
        if fix:
            c.execute("UPDATE tasks SET status='ready' WHERE id=? AND status='todo'", (r[0],))
    
    # 2. Running tasks with no heartbeat
    c.execute("SELECT id, worker_pid, title FROM tasks WHERE status='running' AND worker_pid IS NOT NULL AND last_heartbeat_at IS NULL")
    for r in c.fetchall():
        tid, pid, title = r
        alive = False
        if pid:
            try: os.kill(pid, 0); alive = True
            except OSError: pass
        issues.append({'board': board_name, 'type': 'no-heartbeat', 'id': tid, 'detail': f'pid={pid} alive={alive}'})
        if fix and alive:
            os.kill(pid, 9)
            c.execute("UPDATE tasks SET status='ready', claim_lock=NULL, worker_pid=NULL, current_run_id=NULL WHERE id=?", (tid,))
    
    # 3. Ghost profiles
    placeholders = ','.join(['?'] * len(VALID_PROFILES))
    c.execute(f"SELECT id, status, title, assignee FROM tasks WHERE status NOT IN ('done','archived') AND assignee NOT IN ({placeholders})", VALID_PROFILES)
    for r in c.fetchall():
        issues.append({'board': board_name, 'type': 'ghost-profile', 'id': r[0], 'detail': f'{r[1]} {r[3]} — {r[2][:50]}'})
    
    # 4. Stuck todo (non-review)
    c.execute(f"SELECT id, title, assignee FROM tasks WHERE status='todo' AND title NOT LIKE '%Review%' AND assignee IN ({placeholders})", VALID_PROFILES)
    for r in c.fetchall():
        issues.append({'board': board_name, 'type': 'stuck-todo', 'id': r[0], 'detail': f'{r[2]} — {r[1][:50]}'})
        if fix:
            c.execute("UPDATE tasks SET status='ready' WHERE id=? AND status='todo'", (r[0],))
    
    conn.commit()
    conn.close()
    return issues


def main():
    fix = '--fix' in sys.argv
    json_out = '--json' in sys.argv
    
    all_issues = []
    for d in sorted(os.listdir(BOARDS_DIR)):
        db_path = os.path.join(BOARDS_DIR, d, 'kanban.db')
        if not os.path.exists(db_path): continue
        try:
            all_issues.extend(audit_board(db_path, d, fix=fix))
        except sqlite3.Error as e:
            all_issues.append({'board': d, 'type': 'CORRUPT-DB', 'id': 'N/A', 'detail': f'sqlite3.Error: {e}'})
            print(f"  [{d:16s}] CORRUPT-DB — {e}", file=sys.stderr)
    
    if json_out:
        print(json.dumps(all_issues, indent=2))
    elif not all_issues:
        print("All boards clean — no issues found.")
    else:
        print(f"Found {len(all_issues)} issues across boards:\n")
        for i in all_issues:
            print(f"  [{i['board']:16s}] {i['type']:15s} {i['id']} — {i['detail']}")
        if fix:
            print("\nFixes applied.")
        else:
            print("\nRun with --fix to apply fixes automatically.")

if __name__ == '__main__':
    main()
