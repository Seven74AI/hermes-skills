# Smart Zone vs Turn Budget — two different problems

## The two concepts

| | Turn budget (our checkpoint system) | Token budget (Matt Pocock's smart zone) |
|---|---|---|
| **What it measures** | Iteration count (tool calls) | Tokens accumulated in context window |
| **Failure mode** | Gateway kills worker, work lost | LLM enters "dumb zone" — makes dumb errors, degrades quadratically |
| **Threshold** | 90 turns hard limit, 60-turn checkpoint | ~100K tokens is the danger zone |
| **Matt Pocock's take** | Not his concept | His core concept — "The smart and dumb zone" |

## The false-positive problem

A worker doing everything RIGHT can hit the 60-turn checkpoint with a tiny context:

```
turn 1-5:   download + extract audio (5 turns, ~2K tokens)
turn 6:     launch transcription with background=true + notify_on_complete (1 turn)
turn 7-55:  heartbeats while waiting for transcription (49 turns, ~200 tokens each)
turn 56:    process(action="wait") — but too late, budget already at 60
```

Result: blocked with "budget checkpoint" — but the worker has ~4K tokens of context. Nowhere near the dumb zone. Transcription finished 6 minutes after the block anyway.

## Real case: default board, Ep.05 (2026-05-24)

- Task: Download 443 MB video from Mega.nz, extract WAV, transcribe 28-min French audio with faster-whisper small (CPU)
- Worker: correct pattern — background transcription, heartbeats every 5 min
- Blocked at turn 60 (66%) — transcript was at 30 min of a ~40-min job
- Transcript JSON appeared 6 min after block — work was effectively done
- False positive: no token accumulation, just turn accumulation from waiting

## Matt Pocock's original recommendations (hermes-ops audit, section 7)

From the Obsidian note `Knowledge base/matt-pocock-workflow-audit.md`:

1. **Fix `max_iterations: 120` on all profiles** (reviewer, researcher) — DONE
2. **Add proactive "Smart Zone" check** — after ~70K tokens estimated (based on accumulated messages), worker should consider `kanban_block` + handoff rather than continue — NOT YET IMPLEMENTED
3. **Formalize Memento Pattern** at 60% budget — DONE (our 60-turn checkpoint)

Note: recommendation #2 is about TOKENS, not turns. We haven't implemented token tracking.

## What we actually need

A token-aware checkpoint, not just turn-counting. The gateway could:
- Track cumulative input tokens per run
- Fire a "smart zone" warning at ~70K tokens
- Fire a hard checkpoint at ~90K tokens (before the 100K dumb zone)

Until then, the turn-budget checkpoint has this known blind spot for background-wait workloads.

## Fix applied (2026-05-24)

The Ep.05 false positive was caused by the worker using **heartbeats** (1 turn each)
to poll a background transcription instead of `process(action="wait")` (1 turn
total). Changes made:

1. **`researcher-videos/SOUL.md`** — TOKEN ECONOMY section now mandates
   `background=true` + `process(action="wait")` for ALL long-running background
   tasks (transcription, Mega downloads, ffmpeg, git clones). Explicit example
   and "never use heartbeats to wait" rule.

2. **`kanban-worker/SKILL.md`** — Budget checkpoint section now includes an
   explicit warning: heartbeats during background waits are the #1 cause of
   false-positive budget blocks. Workers are told to use `process(action="wait")`
   instead of polling.

### The pattern every worker MUST use for background tasks

```python
# Launch in background
terminal("heavy_task.sh", background=True, notify_on_complete=True)
# Wait — single call, blocks without burning turns
process(action="wait", timeout=7200)
# Read result
read_file("/tmp/result.json")
```

This is 3 turns instead of 30-50. The `process wait` is the key — it blocks
the agent turn without consuming iterations, unlike polling heartbeats which
burn 1 turn each.
