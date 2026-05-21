# test:all Script Pattern

The single most effective defense against iteration budget exhaustion: a combined
`test:all` script in `package.json` that runs unit + E2E tests in one command.

## Why

Workers given separate `test` and `test:e2e` scripts will run them inline one after
another, burning 50-200 iterations on test output. A single `test:all` command,
called in background+wait, burns 2-3 iterations total.

## The script

```json
// package.json
{
  "scripts": {
    "test": "vitest run",
    "test:e2e": "playwright test",
    "test:all": "tsc --noEmit && vitest run && playwright test"
  }
}
```

## Worker usage (SOUL.md)

```
# RIGHT — 2-3 turns total
terminal("pnpm test:all", background=true, notify_on_complete=true)
process(action="wait", timeout=3600)
read_file("test-results.json")
```

## Per-project variants

| Stack | Command |
|-------|---------|
| Vitest + Playwright | `vitest run && playwright test` |
| Jest + Cypress | `jest --ci && cypress run` |
| Pytest + Selenium | `pytest && pytest --e2e` |
| Godot | `godot4 --headless --quit --path . 2>&1` (single check) |

## Pre-commit hooks

The `test:all` script bypasses the pre-push hook's `vitest run --changed` check.
That's fine — the hook runs on `git push`, the full suite runs in background.
The hook catches fast regressions; the background suite is the authoritative gate.

## Real case

t_8228590c on the-swarm board, 2026-05-20:
- Run #571: ran E2E inline → 90/90 iterations exhausted, 58min wasted
- Run #573: same task, same mistake → protocol violation crash, 41min wasted
- Run #579: SAME TASK, SAME MISTAKE → idle 36min, reclaimed
- 3 runs, ~3h wasted, zero progress

After adding `test:all` to package.json and updating SOUL.md, the next run
completed in 1 attempt.
