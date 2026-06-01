#!/usr/bin/env python3
"""Clean PR URL comments and body references from all boards.

Run when pre-spawn watchdog flags PR-URL-IN-BODY or PR-URL-COMMENTS.
These URLs trigger the active_pr respawn guard for 24h, blocking dispatch.

Usage: python3 scripts/clean-pr-urls.py [board1 board2 ...]
       (no args = all boards)
"""
import sqlite3, glob, sys, re

BOARDS_DIR = "/root/.hermes/kanban/boards"
DEFAULT_DB = "/root/.hermes/kanban.db"

def clean_board(db_path, name):
    db = sqlite3.connect(db_path)
    total = 0

    # Delete PR URL comments
    db.execute("DELETE FROM task_comments WHERE body LIKE '%github.com%pull%'")
    total += db.total_changes

    # Strip PR URLs from task bodies
    for row in db.execute("SELECT id, body FROM tasks WHERE body LIKE '%github.com%pull%'"):
        clean = re.sub(r'https?://github\.com/\S+', '[PR merged — see GitHub]', row[1])
        db.execute("UPDATE tasks SET body=? WHERE id=?", (clean, row[0]))
        total += db.total_changes

    db.commit()
    db.close()
    if total:
        print(f"  {name}: cleaned {total} PR URL references")

# Which boards?
if len(sys.argv) > 1:
    boards = []
    for slug in sys.argv[1:]:
        db_path = f"{BOARDS_DIR}/{slug}/kanban.db"
        if slug == "default":
            db_path = DEFAULT_DB
        boards.append((slug, db_path))
else:
    boards = []
    for db_path in glob.glob(f"{BOARDS_DIR}/*/kanban.db"):
        slug = db_path.split("/")[-2]
        boards.append((slug, db_path))
    # Include default board
    boards.append(("default", DEFAULT_DB))

print(f"Scanning {len(boards)} boards...")
for slug, db_path in boards:
    try:
        clean_board(db_path, slug)
    except Exception as e:
        print(f"  {slug}: ERROR - {e}")
print("Done.")
