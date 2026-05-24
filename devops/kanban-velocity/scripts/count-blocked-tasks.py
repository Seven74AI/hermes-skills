#!/usr/bin/env python3
"""Count blocked tasks across all boards. Useful for monitoring kanban health."""

import subprocess

boards_raw = subprocess.run(
    "hermes kanban boards list", shell=True, capture_output=True, text=True
).stdout

total = 0
for line in boards_raw.splitlines():
    line = line.strip()
    if not line or line.startswith("Board"):
        continue
    parts = line.split()
    if not parts:
        continue
    b = parts[0].rstrip("*")
    try:
        out = subprocess.run(
            f"hermes kanban --board {b} stats 2>/dev/null",
            shell=True, capture_output=True, text=True,
        ).stdout
        for sl in out.splitlines():
            if "blocked" in sl:
                total += int(sl.split()[-1])
    except Exception:
        pass

print(total)
