#!/usr/bin/env python3
"""Wrapper: runs both check-blocked-tasks.py and check-crash-loops.py.
Outputs concatenated results from both scanners.

Blocked tasks:   check-blocked-tasks.py  (scans --status blocked)
Crash loops:     check-crash-loops.py    (scans running + consecutive_failures >= 5)
"""

import subprocess, sys, os

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

scripts = [
    "check-blocked-tasks.py",
    "check-crash-loops.py",
]

had_output = False
for script in scripts:
    path = os.path.join(SCRIPTS_DIR, script)
    result = subprocess.run(
        [sys.executable, path],
        capture_output=True, text=True, timeout=60,
        env={**os.environ},
    )
    if result.stdout.strip():
        sys.stdout.write(result.stdout)
        had_output = True
    if result.stderr.strip():
        sys.stderr.write(result.stderr)

# If both scripts were silent (OK), emit nothing
if not had_output:
    pass  # silent watchdog — cron delivers nothing
