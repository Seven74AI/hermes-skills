---
name: long-running-tests
description: "Use when running test suites, benchmarks, or validation scripts that would exceed 90-turn iteration budget. Core pattern: background+notify+wait — never run test suites inline in the agent loop."
version: 2.3.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [testing, background, timeout, pattern, iteration-budget, kanban]
    related_skills: [kanban-worker, test-driven-development, project-ci, spike]
---

# Long-Running Test Suites — Agent Iteration Budget Pattern

## Overview

Hermes agents have a **90-turn iteration budget**. Each tool call consumes one iteration. Running test suites inline triggers a fix-and-retry loop: run tests (1 iter) → inspect output (1 iter) → fix code (1 iter) → re-run tests (1 iter) → repeat. Each cycle burns 3-5 iterations, and a 5-cycle debug session alone costs 15-25 iterations. This, not raw test output, is the #1 cause of budget exhaustion on coding tasks.

**The fix is NOT splitting into smaller tasks (alone).** The fix is to run test suites OUTSIDE the agent loop using `terminal(background=true, notify_on_complete=true)` + `process(action="wait")`. The agent only calls this once (1 iteration), then waits for the result (0 iterations). The entire test suite runs independently with zero iteration cost.

## When to Use

Load this skill when:
- Running any test suite >10 tests (Playwright, Vitest, Godot/GUT, pytest, etc.)
- Running benchmarks or performance validation scripts
- A task has been blocked 2+ times with "Iteration budget exhausted"
- Setting up CI validation tasks that run full test suites
- You find yourself typing `npx playwright test` or `npm test` directly in `terminal()`

**Do NOT use inline test runs.** Running tests inline locks you into the fix-and-retry loop: each test→fix→retest cycle burns 3-5 iterations. A 200-test Playwright suite might need 3-4 cycles, costing 12-20 iterations just in overhead — before any actual debugging.

## Core Pattern: Background + Notify + Wait

### The One True Way

```
1. terminal("run-test-suite.sh", background=true, notify_on_complete=true, timeout=3600)
   → Returns session_id → 1 iteration spent

2. process(action="wait", timeout=3600)
   → Blocks WITHOUT consuming iterations → 0 iterations spent

3. Read results, fix if needed, complete
   → 2-3 iterations to read output and act
```

Total cost: ~5 iterations for the ENTIRE test cycle, regardless of suite size.

### Example: Playwright Suite

```bash
# Start dev server + run tests in one background script
terminal(
  command="npx playwright test --workers=1 2>&1 | tee /tmp/test-output.txt",
  background=true,
  notify_on_complete=true,
  timeout=1800,
  workdir="/path/to/project"
)
# Returns: {"session_id": "abc123"}

# Wait (0 iterations)
process(action="wait", timeout=1800)

# Read results (1 iteration)
read_file("/tmp/test-output.txt", offset=1, limit=50)
```

### Example: Godot Headless Validation

```bash
terminal(
  command="godot4 --headless --quit --path /path/to/project/ 2>&1 | tee /tmp/godot-output.txt",
  background=true,
  notify_on_complete=true,
  timeout=600
)
process(action="wait", timeout=600)

# Check for errors in output
search_files(pattern="ERROR:|SCRIPT ERROR:|FATAL:", path="/tmp/godot-output.txt")
```

### Example: Single Test File (start server, then test)

```
# Step 1: Start dev server in background (stays alive)
terminal("npm run dev", background=true, workdir="/path/to/project")
# Returns: {"session_id": "srv123"}

# Step 2: Wait for server ready (curl health check)
terminal(
  "for i in $(seq 1 30); do curl -sf http://localhost:3000 && break; sleep 2; done",
  timeout=120,
  workdir="/path/to/project"
)

# Step 3: Run tests against running server
terminal(
  "npx playwright test tests/checkout.spec.ts --workers=1 2>&1 | tee /tmp/test-out.txt",
  background=true,
  notify_on_complete=true,
  timeout=600,
  workdir="/path/to/project"
)
process(action="wait", timeout=600)
```

## Self-Contained Script Pattern (for Multi-Step Loops)

When the work is fundamentally iterative (benchmark → tweak → re-benchmark → compare), put the ENTIRE loop inside a single shell script. The worker calls it ONCE in background.

### Template

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] Baseline benchmark..."
./scripts/benchmark.sh --runs 3

echo "[2/3] Applying optimizations..."
# ... transformations ...

echo "[3/3] Optimized benchmark..."
./scripts/benchmark.sh --runs 3

echo "DONE. Results in benchmark-results.json"
```

### Task Body After Script Creation

```
1. terminal("./scripts/loop.sh", background=true, timeout=7200, notify_on_complete=true)
2. Wait for notification (DO NOTHING ELSE)
3. Read results and commit/complete
```

No room for the worker to iterate inline.

## Phased Splitting (for Large Migrations)

When the WORK ITSELF cannot fit in one run (e.g., migrating 200+ tests to a new framework), split into phases. This is the ONLY valid use of splitting — split because the work is large, not because you're running tests inline.

### Godot/GUT Migration Example

```
[1/4] Install GUT addon + .gutconfig.json          (60s, 0 tests)
[2/4] Migrate first 10 test files → GUT API          (120s, validate 10)
[3/4] Migrate remaining 10 test files → GUT API      (120s, validate 10)
[4/4] Full GUT suite + coverage CI                   (180s, validate all)
```

Each phase uses background+notify+wait for its own validation. No phase burns iterations on test output.

## Why NOT Inline: The Numbers

| Approach | Iterations used | Wall clock | Budget left |
|----------|----------------|------------|-------------|
| Inline `npx playwright test` (200 tests) | 50-80 | 5 min | 10-40 |
| Inline `npm test` (500 unit tests) | 60-90 | 3 min | 0-30 |
| Background + wait (any size) | 3-5 | 5 min | 85-87 |
| Self-contained script (multi-step) | 3-5 | 15 min | 85-87 |

**Inline test runs are NEVER acceptable.** The iteration cost comes from repeated fix-and-retry cycles, not raw output volume. A fast suite with verbose output triggers more inspect→fix→retest cycles, which is WORSE than a slow suite that passes cleanly.

## Common Pitfalls

### 1. Polling After Background Launch (process poll / terminal polling loops)

```bash
# WRONG — burns 50-100 iterations, user-visible annoyance
terminal("npm test", background=true, notify_on_complete=true)
# Then in a loop:
terminal("tail /tmp/test-output.txt")        # iteration 2
process(action="poll", session_id="...")      # iteration 3 — user hates this
terminal("sleep 10")                          # iteration 4
terminal("tail /tmp/test-output.txt")         # iteration 5
# ... repeat 50 times ...
```

**⛔ The user EXPLICITLY rejects this.** They said: "Why you polling? You should run background tasks." Polling is NOT just wasteful — it's a user-visible pattern of inactivity. Every poll is a turn where the agent does nothing useful.

**Fix:** Use `process(action="wait", timeout=3600)` — blocks without consuming iterations. OR, even better, use `terminal(background=true, notify_on_complete=true)` and let the notification come to you. Then use the time to do other work (investigate other tests, check CI logs, review related PRs).

### 2. Running Tests in the Agent Loop

```
# WRONG — each fix-and-retry cycle burns 3-5 iterations
terminal("npx playwright test")  # triggers inspect→fix→retest loop
```

**Fix:** Always use `background=true, notify_on_complete=true`.

### 3. process wait with Too-Short Timeout

```
# WRONG — timeout too short, will miss completion
process(action="wait", timeout=60)  # Test suite takes 5 min
```

**Fix:** Set timeout generously (2-3x expected duration). There's no penalty for setting it high — it returns instantly when done.

### 3b. ⛔ `process(action="wait")` Timeout Clamping — The Real Fallback

**`process(action="wait", timeout=N)` silently clamps to ~60s maximum.** Every wait call
in this session returned `"timeout_note": "Requested wait of 600s was clamped to configured
limit of 60s"` regardless of the requested timeout. The documented pattern (launch background
+ wait) still works for short suites under 60s, but long suites (Playwright 117+ tests,
Godot full builds) will never complete within the clamped window.

**Real working fallback for long suites:**

```
1. terminal("run-tests.sh", background=true, notify_on_complete=true, timeout=3600)
   → Returns session_id

2. process(action="poll", session_id="...")   ← check status (1 iter, sparse — 2-4 calls)
   Check uptime_seconds and status. If "running" and < expected duration, move on.

3. Read output from a log FILE, not from process output:
   terminal("tail -20 /tmp/test-output.log")   ← 1 iter
   OR read_file("/tmp/test-output.log")
   The background command MUST tee output to a file ("> /tmp/test-out.log 2>&1").

4. When process(action="poll") shows status="exited", read the final results.
```

**Why this works:** The notification fires on exit — you don't need to block. Between
launch and notification, poll 2-3 times to check progress (uptime_seconds, log file growth).
Each poll + log read costs 1-2 iterations but the total is ~5 iter vs 50-80 inline.

**Alternative — use `execute_code` for the polling loop?** NO. `execute_code` scripts
also timeout (300s observed) and the `terminal()` calls inside them block. The Python
`time.sleep()` loop approach is worse than direct poll calls from the agent.

**Key rule for the log file:** Always redirect background output to a file so you can
read it mid-run:
```bash
terminal(
  command="pnpm playwright test --workers=1 > /tmp/playwright-out.log 2>&1",
  background=true,
  notify_on_complete=true,
  timeout=1800
)
# Then poll + read_file("/tmp/playwright-out.log") every few minutes
```

### 4. Using kanban_block Instead of process wait

```
# WRONG — fragments the task, requires re-dispatch
terminal("npm test", background=true, notify_on_complete=true)
kanban_block(reason="tests running, will resume when done")
```

**Fix:** Use `process(action="wait")` to stay in the same run. Blocking mid-work causes re-dispatch, losing context and restarting from scratch.

### 5. Not Using notify_on_complete

```
# WRONG — you'll never know when it finishes
terminal("npm test", background=true)
# Now what? Polling, sleeping, guessing...
```

**Fix:** Always pair `background=true` with `notify_on_complete=true` for finite tasks.

### 6. Killing a Background Process Without Checking Expected Duration

```
# WRONG — kills work that was almost done
# Worker spawned a 2-hour audio transcription on CPU (~3× realtime = 6h expected)
# After 5h elapsed, agent assumes "stuck" and kills it
# Result: 5h of CPU lost, transcription restarted from zero
```

**Fix:** Before killing ANY long-running background process, compute the expected duration:
- **Whisper transcription (CPU):** file duration × 3-5 for large-v3, × 2-3 for small
- **Video download (yt-dlp):** file size / rate limit (plus ~30% overhead)
- **Test suite:** check historical run time from CI logs
- **Build/install:** check package count or previous runs

Compare expected duration against elapsed time. A process at 80% of expected wall time is likely finishing, not stuck. **Only kill when elapsed > 2× expected duration with zero progress (no output file growth, no log activity).**

**Real case (2026-05-27):** 121-minute MP3, small model on CPU, expected ~5h. Process at 5h elapsed, killed. User: "C'est ptet normal" — it was. File was 2h long, transcription was almost done.

## Cron Alternative (Recurring Validation)

For CI pipelines or recurring test runs where no agent reasoning is needed:

```bash
cronjob(
  action="create",
  schedule="every 30m",
  script="ci-run-tests.sh",
  no_agent=true
)
```

The script runs tests. Non-empty stdout is delivered verbatim. Empty stdout = silent (nothing to report). Non-zero exit = error alert. Zero tokens consumed.

## max_runtime Guidelines

Set `max_runtime_seconds` generously — 2-3x expected duration. The dispatcher uses this to detect stuck tasks, not to limit work.

| Task type | Recommended max_runtime | Why |
|-----------|------------------------|-----|
| Install/setup | 120s | Package downloads can be slow |
| Single test file (background) | 300s | Includes server start + test |
| Full test suite (background) | 1800s | 30 min for large suites |
| Self-contained loop script | 3600s | Multi-step benchmark cycles |
| CI validation (cron) | N/A | Runs outside dispatcher |

## Pre-Review Validation (Godot / Game Projects)

Before marking a game project task as review-ready, validate headlessly:

```bash
terminal(
  "godot4 --headless --quit --path <project>/ 2>&1",
  background=true,
  notify_on_complete=true,
  timeout=300
)
process(action="wait", timeout=300)
```

Requirements for passing:
- Exit code 0
- Zero `ERROR:`, `SCRIPT ERROR:`, or `FATAL:` lines in output
- Include full output in handoff comment for reviewer

## Verification Checklist

- [ ] No `terminal("... test ...")` calls WITHOUT `background=true`
- [ ] Every background test run has `notify_on_complete=true`
- [ ] `process(action="wait")` used instead of polling loops
- [ ] Test scripts output to a file for post-mortem reading
- [ ] `max_runtime_seconds` is 2-3x expected duration
- [ ] Multi-step loops use self-contained scripts (not inline iteration)
- [ ] Pre-review validation runs headlessly and passes cleanly
