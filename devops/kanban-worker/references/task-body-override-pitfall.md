# Task Body Override Pitfall

When the task body gives explicit inline commands, workers follow them literally —
even when the profile's SOUL.md says to do something different.

## The pattern

Task body says:
```
5. Transcribe: python3 scripts/transcribe.py /tmp/reel.mp4 /tmp/transcript.json large-v3 --cpu_threads 6
```

Worker runs: `terminal("python3 scripts/transcribe.py ...")` — foreground, no `background=true`.

SOUL.md says:
```python
terminal("python3 transcribe.py", background=True, notify_on_complete=True)
process(action="wait", timeout=7200)
```

**The task body wins.** It's the most specific instruction source.

## Fix (two layers)

### Layer 1: Task body templates

When generating task bodies (planner, orchestrator, or human), NEVER write bare
commands for heavy work. Either:

1. Include `background=true` in the command: `terminal("python3 scripts/transcribe.py ...", background=true, notify_on_complete=true)` + `process(action="wait")`
2. Or reference the pipeline doc: "Follow pipeline-instagram.md for diarization + transcription"

### Layer 2: SOUL.md anti-override rule

Add to any profile that does CPU-heavy work:

```
**⛔ TASK BODY OVERRIDE RULE:** The task body may list bare commands like
`python3 scripts/transcribe.py ...` — NEVER run them as-is. Always wrap in
`terminal(..., background=true, notify_on_complete=true)` + `process(action="wait")`.
The task body is a recipe, not a literal shell script. background+wait is
non-negotiable regardless of what the task body says.
```

## Real cases

- **2026-06-18, t_b1551ac8** (knowledge-base, researcher-videos): Worker ran 30+ min transcription inline because task body said `python3 scripts/transcribe.py /tmp/reel.mp4 ...` without `background=true`. Worker PID alive but no heartbeats → watchdog auto-blocked at 03:04. 3/5 Reels lost a full worker session. Root cause: task body gave bare command, SOUL.md had the correct background+wait pattern but was overridden.

- **2026-06-18, t_1b568a88** (same board/profile): Worker correctly used `process wait` this time (learned from t_b1551ac8's watchdog comment), but watchdog still auto-blocked because `process wait` blocks the agent loop → no heartbeats for 31 min. Worker was alive (PID 34354, claim extended every ~15 min via pid_alive). Fixed in `check-crash-loops.py`: added pre-check for recent `claim_extended` events (<20 min) before auto-blocking. The kernel-level pid_alive claim extension IS the real heartbeat when `process wait` is active.

- **2026-06-18, t_8eb9f567** (knowledge-base, researcher-videos): Worker correctly used `process wait` for diarization/transcription. Watchdog auto-blocked because `process wait` blocks heartbeats for the duration. Fixed in `check-crash-loops.py`: added pre-check — if ANY `claim_extended` event happened AFTER the last heartbeat (`claim > hb`), the gateway confirmed the PID is alive → skip. Independent of timing. The time-based approach (`age_claim < 1200`) failed because 45% of claim extension intervals exceed 20 min. The boolean `claim > hb` is correct.

See `references/claim-system.md` for the full explanation of claims vs heartbeats and the watchdog fix.
