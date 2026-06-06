# Continuation Child + Planner Chain Collision — Full Diagnostic

## Date: 2026-06-05
## Board: default
## Affected tasks: t_123f6f1b, t_0f11f419, t_d00baacc
## Profile: researcher-videos (whisper large-v3 CPU transcription)

## Collision Mechanism

```
PLANNER (June 1):
  t_8a63b9b9 (batch 1) → t_6d953883 (batch 2) → t_0f11f419 (batch 3) → t_9859d5f8 (batch 4)

WORKER on t_6d953883 (June 5, run #115):
  Processed 2/5 reels → created continuation child t_d00baacc for remaining 3
  → kanban_complete with created_cards=[t_d00baacc]

PARENT COMPLETION (11:17):
  t_0f11f419 promoted (planner chain: parent completed)
  t_d00baacc promoted (continuation child: parent completed)
  BOTH become ready simultaneously

DISPATCHER (11:18):
  Spawned t_0f11f419 (PID 2116111) + t_d00baacc (PID 2116138)
  t_123f6f1b (PID 2086355) already running since 10:24

RESULT:
  3 researcher-videos workers → 4 concurrent whisper large-v3 processes
```

## System Impact

| Metric | Value | Normal |
|--------|-------|--------|
| Load avg | 11.69 | <4 |
| CPU pressure (some) | 42% | <5% |
| RAM used | 9.2/11 GB | ~4GB |
| Swap used | 5.7/9 GB | ~1GB |
| Concurrent whisper | 4 processes | 1-2 max |
| Whisper CPU total | ~377% | ~100% per process |
| Whisper RAM total | ~9.1 GB | ~2-3 GB |

## Per-Process Detail

| PID | Worker | Reel | CPU% | RSS |
|-----|--------|------|------|-----|
| 2121346 | t_123f6f1b | DXpAMjkDKxz | 93.8% | 3.0GB |
| 2118848 | t_0f11f419 | DVzAWsEko0Q | 95.7% | 2.1GB |
| 2118915 | t_0f11f419 | DY5AznXN-f7 | 97.1% | 2.1GB |
| 2118513 | t_d00baacc | DZALCSBNft- | 90.4% | 1.9GB |

## Timeline

- 10:24 — t_123f6f1b run #114 spawned (1 reel)
- 10:24 — t_6d953883 run #115 spawned (batch 2, 5 reels)
- 11:17 — t_6d953883 completed (2/5 done), created t_d00baacc
- 11:17 — t_0f11f419 promoted (parent completed)
- 11:17 — t_d00baacc promoted (parent completed)
- 11:18 — t_0f11f419 run #117 + t_d00baacc run #118 spawned
- 11:21 — t_0f11f419 launched 2 parallel whisper processes
- 11:26 — t_123f6f1b heartbeat: "6 concurrent whisper processes on this host causing resource contention"

## Root Cause

The dispatcher sees tasks, not resource requirements. Two children of the same parent became `ready` simultaneously — one from the planner's sequential chain, one from the worker's continuation pattern. The dispatcher correctly dispatched both since spawn slots were available. Neither the dispatcher nor the workers knew the tasks were CPU-heavy and mutually destructive when run in parallel.

## Fix Applied

Memento Pattern instead of continuation children for CPU-heavy batch work. Worker blocks the SAME task with a handoff instead of creating a new child. One task = one worker at a time = no parallel collision.
