#!/usr/bin/env python3
"""Detect kanban tasks stuck in crash loops (running + high consecutive_failures).

Unlike check-blocked-tasks.py which only scans --status blocked,
this scanner reads the kanban SQLite DB directly to find running tasks
that are silently crash-looping. These are invisible to the block watchdog
because the dispatcher keeps respawning them.

Threshold: consecutive_failures >= CRASH_LOOP_THRESHOLD (default 5).
Auto-block: if AUTO_BLOCK=true (default), tasks exceeding threshold are
blocked to stop the dispatcher wasting resources on them.

Usage:
    python3 check-crash-loops.py
    AUTO_BLOCK=false python3 check-crash-loops.py   # report only
"""

import sqlite3, os, sys, time
from pathlib import Path

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from watchdog_lib import emit_batch_report

KANBAN_BASE = Path("/root/.hermes/kanban/boards")
CRASH_LOOP_THRESHOLD = int(os.environ.get("CRASH_LOOP_THRESHOLD", "5"))
AUTO_BLOCK = os.environ.get("AUTO_BLOCK", "true").lower() == "true"
NOW = time.time()


def block_task(board: str, task_id: str, reason: str) -> bool:
    """Block a task via hermes kanban CLI."""
    import subprocess, shlex
    try:
        subprocess.run(
            f"hermes kanban --board {board} block {task_id} {shlex.quote(reason)}",
            shell=True, capture_output=True, text=True, timeout=15,
        )
        return True
    except Exception as e:
        print(f"  WARNING: block failed for {board}/{task_id}: {e}", file=sys.stderr)
        return False


def format_time_ago(ts: float) -> str:
    delta = NOW - ts
    if delta < 60:
        return f"{int(delta)}s"
    if delta < 3600:
        return f"{int(delta/60)}m"
    if delta < 86400:
        return f"{int(delta/3600)}h"
    return f"{int(delta/86400)}d"


def main():
    boards = []
    for entry in sorted(KANBAN_BASE.iterdir()):
        if entry.is_dir() and (entry / "kanban.db").exists():
            boards.append(entry.name)

    if not boards:
        emit_batch_report(
            name="crash-loop-watchdog",
            severity="OK",
            summary="No boards found",
            items=[],
        )
        return

    crash_tasks = []
    auto_blocked = []

    for board in boards:
        db_path = KANBAN_BASE / board / "kanban.db"
        try:
            db = sqlite3.connect(str(db_path))
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """SELECT id, title, assignee, status, consecutive_failures,
                          created_at, started_at, last_failure_error
                   FROM tasks
                   WHERE status = 'running'
                     AND consecutive_failures >= ?
                   ORDER BY consecutive_failures DESC""",
                (CRASH_LOOP_THRESHOLD,),
            ).fetchall()
            db.close()
        except Exception as e:
            print(f"  WARNING: DB read failed for {board}: {e}", file=sys.stderr)
            continue

        for row in rows:
            task_id = row["id"]
            failures = row["consecutive_failures"]
            title = row["title"] or "(untitled)"
            assignee = row["assignee"] or "?"
            started = row["started_at"] or 0
            age = format_time_ago(started) if started else "?"
            error = (row["last_failure_error"] or "")[:80]

            entry = (
                f"{board}/{task_id}: {failures}x crashes | "
                f"@{assignee} | since {age} ago"
                + (f" | {error}" if error else "")
                + f" | {title[:60]}"
            )
            crash_tasks.append(entry)

            if AUTO_BLOCK:
                reason = (
                    f"Watchdog auto-block: {failures}x consecutive crashes "
                    f"(threshold={CRASH_LOOP_THRESHOLD}). "
                    f"Running since {age} ago. Human review needed."
                )
                if block_task(board, task_id, reason):
                    auto_blocked.append(f"{board}/{task_id} → blocked ✓")

    if not crash_tasks:
        emit_batch_report(
            name="crash-loop-watchdog",
            severity="OK",
            summary="No crash loops detected",
            items=[],
        )
        return

    summary_parts = [f"{len(crash_tasks)} task(s) in crash loop"]
    if AUTO_BLOCK and auto_blocked:
        summary_parts.append(f"{len(auto_blocked)} auto-blocked")

    action = None
    if AUTO_BLOCK and auto_blocked:
        action = (
            f"Auto-blocked {len(auto_blocked)} task(s) to stop resource waste. "
            f"Review each blocked task: hermes kanban --board <board> show <id>"
        )
    else:
        action = (
            f"{len(crash_tasks)} task(s) crash-looping. "
            f"Review and manually block if needed."
        )

    emit_batch_report(
        name="crash-loop-watchdog",
        severity="CRITICAL",
        scope=f"{len(boards)} board(s) checked",
        findings=f"{len(crash_tasks)} crash loops" + (
            f", {len(auto_blocked)} auto-blocked" if auto_blocked else ""
        ),
        summary=", ".join(summary_parts),
        items=crash_tasks + ([""] + auto_blocked if auto_blocked else []),
        action=action,
    )


if __name__ == "__main__":
    main()
