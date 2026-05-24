#!/usr/bin/env python3
"""Kanban daily health monitor — velocity + system + blocked tasks.
Designed for no_agent=true cron delivery to Discord.

Usage:
  python3 kanban-daily-monitor.py

Outputs a plain-text report suitable for Discord code blocks.
"""

import re
import subprocess
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
day = now.strftime("%d %b")


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


# Velocity snapshot (latest row only)
vel = run("python3 ~/.hermes/scripts/kanban-velocity-view.py 2>&1")

# System health
disk = run("df -h / | tail -1 | awk '{print $5}'")
mem = run("free -h | awk '/Mem:/{print $3\"/\"$2}'")
load = run("uptime | awk -F'average load:' '{print $2}'").strip()

# Hermes processes
workers = run("ps aux | grep -c '[h]ermes' || echo 0")

# Blocked tasks across all boards
blocked = run("python3 ~/.hermes/scripts/count-blocked-tasks.py 2>&1")

# Extract latest velocity snapshot row (line with date + Done/Total numbers)
latest_vel = "N/A"
for line in vel.splitlines():
    if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+\d+", line):
        latest_vel = line

report = f"""📈 **Kanban Daily Health — {day}**

```
{latest_vel}

Système:
  Disk: {disk}  |  RAM: {mem}  |  Load:{load}
  Processus Hermes: {workers}  |  Tâches bloquées: {blocked}
```
"""

print(report)
