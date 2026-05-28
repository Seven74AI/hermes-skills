#!/usr/bin/env python3
"""Kanban DB integrity watchdog — checks all kanban DBs, alerts on corruption.
   
Runs as a cron job every hour (no_agent=True). Silent when clean (exit 0).
On corruption: prints details, backs up corrupt DB, exits non-zero.
The cron scheduler delivers the alert to Discord and Telegram."""
import sqlite3, os, sys, time, shutil
from pathlib import Path

KANBAN_DIR = Path(os.path.expanduser("~/.hermes/kanban"))

dbs = []

# Dispatcher DB
dispatcher = KANBAN_DIR / "kanban.db"
if dispatcher.exists():
    dbs.append(("dispatcher", dispatcher))

# Board DBs
boards_dir = KANBAN_DIR / "boards"
if boards_dir.is_dir():
    for board_dir in sorted(boards_dir.iterdir()):
        if not board_dir.is_dir():
            continue
        db_path = board_dir / "kanban.db"
        if db_path.exists():
            dbs.append((board_dir.name, db_path))

# Root-level default board (legacy path)
root_db = KANBAN_DIR / "kanban.db"
if root_db.exists() and ("default", root_db) not in dbs:
    dbs.append(("default", root_db))

issues = []

for name, path in dbs:
    try:
        if not path.exists() or path.stat().st_size == 0:
            continue
        conn = sqlite3.connect(str(path), timeout=5)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
        if row and str(row[0]).lower() == "ok":
            continue
        detail = row[0] if row else "no result"
        issues.append(f"{name}: integrity_check={detail}")
        # Auto-backup
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup = path.parent / f"{path.name}.corrupt.{ts}.bak"
        shutil.copy2(path, backup)
    except sqlite3.DatabaseError as e:
        issues.append(f"{name}: DatabaseError: {e}")
    except Exception as e:
        issues.append(f"{name}: Unexpected: {e}")

if issues:
    print(f"CORRUPTION DETECTED — {len(issues)} DB(s):")
    for issue in issues:
        print(f"  {issue}")
    sys.exit(1)
