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

## Token Cost Analysis

The cleanup agent runs an LLM call every tick even when silent — the system prompt, tool schema, and watchdog context are passed to the model regardless of whether it responds with `.` or a full report. This is by design (the agent must evaluate the context to decide silence), but it comes with a real cost.

**Observed costs (DeepSeek v4-pro, 2026-05-21):**
- ~15k input tokens per silent run (system prompt + tools + watchdog output)
- At every 10min: 144 runs/day → ~2.2M input tokens/day
- At every 15min: 96 runs/day → ~1.4M input tokens/day
- Cost: ~$0.20-0.50/day at DeepSeek pricing depending on frequency

**When to run the agent (vs script-only watchdog):**
- Disk below 70% and stable → the agent adds zero value; every response will be `.`
- Disk trending up but <80% → marginal value; mostly reporting trends the watchdog already covers
- Disk ≥80% → the agent IS the cleanup executor; essential

**Frequency recommendation:**
- `every 30m` is sufficient when disk is stable — 48 runs/day, ~$0.10/day
- `every 1h` is reasonable for long-term monitoring — 24 runs/day, ~$0.05/day
- `every 10m` is overkill and wastes tokens with no benefit
- Consider pausing the agent cron entirely when disk has been <70% for >24h; re-enable if the watchdog triggers a WARN

**Detecting silent-waste patterns:**
Check session files for the agent cron — if 95%+ of recent runs contain only `.` as the assistant response, the agent is not providing value. Audit methodology: see `references/cron-audit-methodology.md`.

## Key Design Decisions

- **no_agent for watchdog**: zero token cost in normal operation. Only costs tokens when threshold breached AND cleanup agent activates.
- **context_from chaining**: cleanup agent reads watchdog's most recent completed output. No polling, no duplicate df calls.
- **Stagger schedules**: both at "every 15m" but the cleanup agent naturally runs ~1min after watchdog since it was created second. The context_from injects the latest completed watchdog output.
- **Silent on <50%**: no notification spam. Only alerts when thresholds are hit.
- **Guardrails in the skill, not the script**: the cleanup agent loads the skill which enforces rules (never delete blocked/running workspaces, stop on script failure, etc.). The watchdog script just reports facts.
