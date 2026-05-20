#!/usr/bin/env python3
"""Auto-cleanup kanban workspaces for done/archived tasks across all boards.
Fixed: uses completed_at (Unix timestamp) instead of the non-existent updated_at column."""
import sqlite3, shutil, os, sys

KANBAN_DIR = os.path.expanduser("~/.hermes/kanban/boards")

boards = [d for d in os.listdir(KANBAN_DIR) 
          if os.path.isdir(os.path.join(KANBAN_DIR, d))]

total = 0
for board in boards:
    db_path = os.path.join(KANBAN_DIR, board, "kanban.db")
    ws_base = os.path.join(KANBAN_DIR, board, "workspaces")
    if not os.path.exists(db_path) or not os.path.exists(ws_base):
        continue
    
    try:
        conn = sqlite3.connect(db_path)
        # completed_at is a Unix timestamp (seconds since epoch).
        # Only delete workspaces of tasks completed > 5 minutes ago.
        cutoff = int(time.time()) - 300  # 5 minutes ago
        rows = conn.execute(
            "SELECT id FROM tasks WHERE status IN ('done', 'archived') "
            "AND completed_at IS NOT NULL "
            "AND completed_at < ?", (cutoff,)
        ).fetchall()
        conn.close()
    except Exception as e:
        print(f"[{board}] DB error: {e}", file=sys.stderr)
        continue
    
    for (tid,) in rows:
        ws = os.path.join(ws_base, tid)
        if os.path.exists(ws):
            try:
                shutil.rmtree(ws, ignore_errors=True)
                total += 1
            except Exception:
                pass

if total > 0:
    print(f"Cleaned {total} workspace(s)")
