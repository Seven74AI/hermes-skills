# Disk Watchdog + Cleanup Agent Pattern

Two-cron pattern for resource monitoring with zero-cost normal operation and full agent cleanup on threshold breach.

## Architecture

```
┌─────────────────────┐     context_from     ┌──────────────────────┐
│  disk-watchdog.py   │ ──────────────────→  │  Disk Cleanup Agent  │
│  no_agent, every 15m│                      │  agent, every 15m    │
│                      │                      │  loads disk-cleanup  │
│  <50% → silent       │                      │  skill               │
│  50-70% → alert      │                      │                       │
│  ≥80% → CLEANUP_     │                      │  no trigger → "."    │
│         TRIGGER=true │                      │  trigger → full run  │
└─────────────────────┘                      └──────────────────────┘
```

## Setup

### 1. Watchdog script (no_agent)

```python
#!/usr/bin/env python3
"""Outputs alerts at thresholds. Exit 0 always."""
import subprocess, sys

df_line = subprocess.run("df -h / | tail -1", shell=True, capture_output=True, text=True).stdout.strip()
parts = df_line.split()
pct = int(parts[4].rstrip('%'))
avail, size = parts[3], parts[1]

if pct >= 80:
    print(f"🚨 CRITICAL: disk {pct}% full ({avail} free / {size} total)")
    print("CLEANUP_TRIGGER=true")
elif pct >= 70:
    print(f"⚠️ WARNING: disk {pct}% full ({avail} free / {size} total)")
elif pct >= 60:
    print(f"⚠️ WARNING: disk {pct}% full ({avail} free / {size} total)")
elif pct >= 50:
    print(f"ℹ️ HEADS-UP: disk {pct}% full ({avail} free / {size} total)")
# <50%: silent
```

### 2. Watchdog cron

```bash
hermes cron create "every 15m" \
  --name "Disk Space Watchdog" \
  --script disk-watchdog.py \
  --no-agent \
  --deliver origin
```

### 3. Cleanup agent cron

```bash
hermes cron create "every 15m" \
  --name "Disk Cleanup Agent" \
  --prompt "Tu es le disk cleanup agent..." \
  --context-from <watchdog_job_id> \
  --toolsets terminal,skills \
  --deliver origin
```

### 4. Agent prompt

```
Tu es le disk cleanup agent. Tu reçois en contexte la sortie du watchdog.

RÈGLES :
- Si le contexte ne contient PAS "CLEANUP_TRIGGER=true" → réponds "." (silencieux)
- Si le contexte contient "CLEANUP_TRIGGER=true" → charge skill_view('disk-cleanup') et exécute Steps 1→3
```

## Key Design Decisions

- **no_agent for watchdog**: zero token cost in normal operation. Only costs tokens when threshold breached AND cleanup agent activates.
- **context_from chaining**: cleanup agent reads watchdog's most recent completed output. No polling, no duplicate df calls.
- **Stagger schedules**: both at "every 15m" but the cleanup agent naturally runs ~1min after watchdog since it was created second. The context_from injects the latest completed watchdog output.
- **Silent on <50%**: no notification spam. Only alerts when thresholds are hit.
- **Guardrails in the skill, not the script**: the cleanup agent loads the skill which enforces rules (never delete blocked/running workspaces, stop on script failure, etc.). The watchdog script just reports facts.
