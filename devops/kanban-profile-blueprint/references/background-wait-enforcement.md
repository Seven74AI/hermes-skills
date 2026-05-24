# Background+Wait Enforcement — SOUL.md is the enforcement layer

## The problem

`kanban-worker` skill documents `background=true` + `process(wait)` exhaustively.
But workers still poll with heartbeats when their profile's SOUL.md doesn't mandate
it explicitly. The skill says HOW; the SOUL must say MUST.

**Real case (2026-05-24):** `researcher-videos` profile had `kanban-worker` loaded.
Worker launched faster-whisper transcription in background, then polled with
`kanban_heartbeat` every 5 minutes. Hit 60-turn budget checkpoint at 66% —
transcription was still running. Transcript finished 6 minutes after the block.
False positive: worker had ~4K tokens of context, nowhere near the dumb zone.

Root cause: SOUL.md's TOKEN ECONOMY section said "Long videos eat turns" but
didn't explicitly mandate `process(wait)`. Worker defaulted to polling.

## The fix: CPU-bound SOUL template

Any profile that does CPU-bound background work (transcription, video encoding,
large downloads, Mega.nz, ffmpeg extraction) MUST include this in its SOUL.md:

```markdown
## TOKEN ECONOMY — background+wait MANDATORY (N turns)

**⛔ <CPU task name> is the #1 turn-killer.** <task> takes X-Y min per <unit>.
If you poll with heartbeats, you'll burn X-Y turns doing nothing. ONE rule:

    terminal("<cmd>", background=True, notify_on_complete=True)
    process(action="wait", timeout=7200)  # 2h max, blocks without burning turns
    read_file("/tmp/result.json")

This applies to ALL long-running background tasks: transcription, Mega downloads
(443 MB+), ffmpeg extraction, large git clones. **`process wait` replaces 30-50
polling iterations.** Never use heartbeats to wait for a background process.
```

## Timeout guidance

- **Tests/builds**: 3600 (1h) — standard in `long-running-tests` skill
- **Transcription (CPU)**: 7200 (2h) — faster-whisper @ 0.7x realtime, 2h video = ~85 min
- **Video encoding**: 7200 (2h)
- **Mega downloads**: 3600 (varies by bandwidth)

`process wait` returns immediately when the process exits — timeout is a ceiling, not a fixed wait.

## Profiles that need this

| Profile | CPU-bound task | Timeout |
|---------|---------------|---------|
| researcher-videos | faster-whisper transcription | 7200 |
| twitter-coder | pytest suite | 3600 |
| coder (any project) | test:all + lint + typecheck | 3600 |

Profiles without CPU-bound tasks (researcher, reviewer, planner) don't need this —
their turns are spent on tool calls that complete instantly.
