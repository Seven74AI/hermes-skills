# Disk Watchdog + On-Demand Cleanup Agent Pattern

Two-component pattern for resource monitoring with zero-LLM-cost normal operation and full agent cleanup triggered only on threshold breach.

## Architecture

```
┌─────────────────────┐  hermes cron run   ┌──────────────────────┐
│  disk-watchdog.py   │ ────────────────→  │  Disk Cleanup Agent  │
│  no_agent, every 10m│  (only at ≥75%)    │  PAUSED by default   │
│                      │                    │  loads disk-cleanup  │
│  <75% → silent/alert │                    │  skill               │
│  ≥75% → CLEANUP_     │                    │                       │
│         TRIGGER=true │                    │  one-shot, then done │
│         + cron run   │                    │                       │
└─────────────────────┘                    └──────────────────────┘
```

**Key difference from old polling pattern:** The cleanup agent no longer runs on a schedule. It is **paused** in the cron system. The watchdog script calls `hermes cron run <cleanup_job_id>` as a subprocess only when disk reaches the threshold. This eliminates all wasted LLM tokens during normal operation.

## Setup

### 1. Watchdog script (no_agent) — with trigger logic

The watchdog runs on a schedule (every 10 min) and emits alerts at each severity level. At the critical threshold (≥75%), it additionally triggers the paused cleanup agent via subprocess:

```python
if pct >= 75:
    emit_report(severity="CRITICAL", action="CLEANUP_TRIGGER=true ...")
    # Trigger the LLM cleanup agent (paused by default, run on-demand only)
    subprocess.run(
        ["hermes", "cron", "run", "<cleanup_job_id>"],
        timeout=120, capture_output=True
    )
elif pct >= 70:
    emit_report(severity="WARN", ...)
# Lower thresholds: silent or alert as desired
```

The `subprocess.run` is synchronous — the watchdog blocks until cleanup completes (or 120s timeout). This is acceptable because cleanup only runs at ≥75% (rare), and the watchdog's stdout (the alert) is delivered to Discord concurrently via the cron delivery mechanism.

### 2. Watchdog cron (no_agent)

```bash
hermes cron create "every 10m" \
  --name "Disk Space Watchdog" \
  --script disk-watchdog.py \
  --no-agent \
  --deliver discord:#alerts
```

### 3. Cleanup agent cron — PAUSED

Create the cleanup agent, then immediately pause it. The watchdog triggers it on demand:

```bash
hermes cron create "every 10m" \
  --name "Disk Cleanup Agent" \
  --prompt "Tu es le disk cleanup agent..." \
  --context-from <watchdog_job_id> \
  --toolsets terminal,skills \
  --deliver origin

# Then pause it — watchdog triggers via hermes cron run
hermes cron pause <cleanup_job_id>
```

### 4. Agent prompt

```
Tu es le disk cleanup agent. Tu reçois en contexte la sortie du watchdog.

RÈGLES :
- Si le contexte ne contient PAS "CLEANUP_TRIGGER=true" → réponds "." (silencieux)
- Si le contexte contient "CLEANUP_TRIGGER=true" → charge skill_view('disk-cleanup') et exécute Steps 1→3
```

## Token Cost Analysis

**Old polling pattern (DEPRECATED):**
- Cleanup agent ran every 10 min regardless of disk state
- ~15k input tokens per silent run (system prompt + tools + watchdog context)
- 144 runs/day → ~2.2M input tokens/day, >95% of responses were "."
- Cost: ~$0.20-0.50/day for zero value when disk is stable

**New on-demand pattern:**
- Cleanup agent runs 0 times/day when disk <75%
- Only invokes LLM when disk actually needs cleanup (rare — a few times per month)
- Token cost during normal operation: **zero**
- Watchdog is no_agent (script-only), also zero token cost

## Key Design Decisions

- **no_agent for watchdog**: zero token cost in normal operation
- **Paused cleanup agent + subprocess trigger**: LLM only runs when work is actually needed. The `hermes cron run` call is synchronous (watchdog blocks until cleanup finishes), which is fine because ≥75% is a rare event.
- **`context_from` chaining**: cleanup agent reads watchdog's most recent completed output. No polling, no duplicate df calls. Works correctly because the watchdog just wrote its output before triggering the cleanup agent.
- **Thresholds emit to Discord**: the watchdog still delivers WARN/CRITICAL alerts to Discord, so the user sees disk warnings without any LLM involvement.
- **Guardrails in the skill, not the script**: the cleanup agent loads the skill which enforces rules (never delete blocked/running workspaces, stop on script failure, etc.).

## Reverting to polling (if needed)

If the subprocess trigger pattern causes issues (e.g., hermes CLI not available in cron context), fall back to the polling pattern by unpausing the cleanup agent:

```bash
hermes cron resume <cleanup_job_id>
```

And removing the `subprocess.run` call from the watchdog script. The cleanup agent will poll every 10 min as before, responding "." when no trigger is present.
