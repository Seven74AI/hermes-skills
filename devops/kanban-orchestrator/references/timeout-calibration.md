# Timeout Calibration for Kanban Tasks

## Rule: Measure first, then set

Default dispatcher timeout is 180s. Different task types need different timeouts. **Always set `--max-runtime` at task creation** based on task type, not after the 3rd timeout.

## Calibration table (from real data)

| Task type | Observed time | Recommended `--max-runtime` |
|-----------|--------------|---------------------------|
| Deep research (web-heavy, multi-source) | 632s | **600–1000s** |
| Light research (1-2 sources) | ~200s | 300s |
| Code implementation (standard feature) | <180s | 180s (default) OK |
| Install/download (npm install, git clone, Playwright browsers) | 61–138s | **120–300s** |
| Test migration (many files, framework install) | 138s | 300s |
| Large refactor (many files) | variable | 300–600s |

## Real cases

- **the-swarm UX research** (2026-05-19): 5× timeout at 187–196s vs 180s limit. Recreated with 1000s, completed in **632s**. 300s would have been borderline.
- **videogame-lab GUT install** (2026-05-19): timeout at 61s vs 60s limit. Needs 120s minimum.
- **videogame-lab GUT migration** (2026-05-19): timeout at 137–138s vs 120s limit. Needs 180–300s.

## Anti-patterns

- **Letting the watchdog unblock 5+ times with the same timeout.** Archive and recreate with the correct runtime.
- **Setting 300s for research tasks.** The UX research took 632s; 300s would still timeout. Err on the high side for research — 600–1000s is cheap, a blocked task is expensive.
- **Setting timeout for code tasks without data.** Most code tasks finish in <180s. Only bump if you see a pattern of timeouts.

## Companion: dependency chains

When tasks B, C, D depend on task A (install/download), create them with `--parent` so they don't dispatch before A completes. Otherwise they timeout in a loop waiting for the missing dependency.
