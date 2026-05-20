# Self-Contained Script Pattern

When a kanban worker repeatedly ignores background-mode instructions and burns iteration budget on inline test runs, the reliable fallback is a self-contained shell script.

## Principle

The worker's instinct is to "do work" inside the agent loop. If you give it a multi-step task (tweak → test → analyze → repeat), it will execute each step inline, consuming iterations on every `npx playwright test` call.

The fix: put the ENTIRE multi-step workflow inside a single shell script. The worker calls it ONCE in background. All iteration happens inside the script (where it costs zero agent iterations).

## Template

```bash
#!/usr/bin/env bash
set -euo pipefail

# Phase 1: Initial state (baseline)
echo "[1/3] Baseline benchmark..."
./scripts/benchmark.sh --runs 3

# Phase 2: Apply changes
echo "[2/3] Applying optimizations..."
# ... sed/awk/python transformations ...

# Phase 3: Verify
echo "[3/3] Optimized benchmark..."
./scripts/benchmark.sh --runs 3

# Report
echo "Done. See benchmark-results.json"
```

## Task body after script creation

The task body should be reduced to 3 steps:

```
1. terminal("./scripts/loop.sh", background=true, timeout=7200, notify_on_complete=true)
2. Wait for notification (DO NOTHING ELSE)
3. Read results and commit/complete
```

No room for misinterpretation.

## When to use this

- Task has 3+ budget-exhaustion retries despite updated body
- Task is fundamentally a loop (benchmark → tweak → re-benchmark)
- The work takes 10+ minutes of wall-clock time

## Real example

`/tmp/music-library/scripts/e2e-iteration-loop.sh` — runs baseline benchmark, applies Playwright optimizations, runs optimized benchmark, prints comparison. Called once in background by the kanban worker. See that file for the full implementation.
