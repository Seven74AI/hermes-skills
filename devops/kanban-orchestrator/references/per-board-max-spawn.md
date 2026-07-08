# Per-Board max_spawn Configuration

The global `kanban.max_spawn` in `config.yaml` applies to all boards, but
individual boards can override it via their `board.json` metadata file.

## How it works

The gateway's `_tick_once_for_board` reads `board.json` metadata on every
dispatch tick. If `max_spawn` is set in the board's JSON, it overrides the
global config value for that board only. Falls back to `kanban.max_spawn` from
`config.yaml` if the board has no override.

Added 2026-07-07 in `gateway/run.py` (lines 5251-5261).

## Setting a per-board cap

```bash
# Edit the board's board.json
# /root/.hermes/kanban/boards/<board-slug>/board.json
```

Add `"max_spawn": N` to the JSON:

```json
{
  "slug": "knowledge-base",
  "name": "Knowledge Base",
  "max_spawn": 1
}
```

Gateway restart required for code changes; board.json changes are read on every
tick (no restart needed for metadata-only changes).

## Use case

Boards with memory-heavy workloads (video processing, large audio transcription)
should cap concurrency to prevent OOM. Example:

| Board | max_spawn | Reason |
|-------|-----------|--------|
| knowledge-base | 1 | Heavy video/audio processing per worker |
| kb-agent | 1 | Research tasks with large context |
| music-library | 5 (global) | Standard code work, low per-worker memory |

## Verification

After restart, check the dispatcher respects per-board caps:

```bash
# Global
grep "max_spawn:" ~/.hermes/config.yaml | grep -v depth

# Per-board overrides
for board in knowledge-base kb-agent; do
  python3 -c "import json; m=json.load(open(f'/root/.hermes/kanban/boards/$board/board.json')); print(f'$board: max_spawn={m.get(\"max_spawn\", \"(global)\")}')"
done
```
