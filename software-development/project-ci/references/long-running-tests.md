# Long-Running Test Suites — Agent Iteration Budget Pattern

**This reference was absorbed from the standalone `long-running-tests` skill (2026-07-05). Load `project-ci`; this reference covers the execution pattern.**

## Overview

Hermes agents have a **90-turn iteration budget**. Each tool call consumes one iteration. Running test suites inline triggers a fix-and-retry loop: run tests (1 iter) → inspect output (1 iter) → fix code (1 iter) → re-run tests (1 iter) → repeat. Each cycle burns 3-5 iterations, and a 5-cycle debug session alone costs 15-25 iterations.

**The fix:** run test suites OUTSIDE the agent loop using `terminal(background=true, notify_on_complete=true)` + `process(action="wait")`. The agent only calls this once (1 iteration), then waits for the result (0 iterations). The entire test suite runs independently with zero iteration cost.

## Core Pattern: Background + Notify + Wait

```
1. terminal("run-test-suite.sh", background=true, notify_on_complete=true, timeout=3600)
   → Returns session_id → 1 iteration spent

2. process(action="wait", timeout=3600)
   → Blocks WITHOUT consuming iterations → 0 iterations spent

3. Read results, fix if needed, complete
   → 2-3 iterations to read output and act
```

Total cost: ~5 iterations for the ENTIRE test cycle, regardless of suite size.

## Examples

### Playwright Suite

```bash
terminal(
  command="npx playwright test --workers=1 2>&1 | tee /tmp/test-output.txt",
  background=true,
  notify_on_complete=true,
  timeout=1800,
  workdir="/path/to/project"
)
process(action="wait", timeout=1800)
read_file("/tmp/test-output.txt", offset=1, limit=50)
```

### Godot Headless Validation

```bash
terminal(
  command="godot4 --headless --quit --path /path/to/project/ 2>&1 | tee /tmp/godot-output.txt",
  background=true,
  notify_on_complete=true,
  timeout=600
)
process(action="wait", timeout=600)
search_files(pattern="ERROR:|SCRIPT ERROR:|FATAL:", path="/tmp/godot-output.txt")
```

## Self-Contained Script Pattern (for Multi-Step Loops)

When the work is fundamentally iterative (benchmark → tweak → re-benchmark), put the ENTIRE loop inside a single shell script. The worker calls it ONCE in background.

## Why NOT Inline: The Numbers

| Approach | Iterations used | Wall clock | Budget left |
|----------|----------------|------------|-------------|
| Inline `npx playwright test` (200 tests) | 50-80 | 5 min | 10-40 |
| Inline `npm test` (500 unit tests) | 60-90 | 3 min | 0-30 |
| Background + wait (any size) | 3-5 | 5 min | 85-87 |
| Self-contained script (multi-step) | 3-5 | 15 min | 85-87 |

## Common Pitfalls

### 1. Polling After Background Launch

```
# WRONG — burns 50-100 iterations
terminal("npm test", background=true, notify_on_complete=true)
terminal("tail /tmp/test-output.txt")        # iteration 2
process(action="poll", session_id="...")      # iteration 3
terminal("sleep 10")                          # iteration 4
# ... repeat 50 times ...
```

**Fix:** Use `process(action="wait", timeout=3600)` — blocks without consuming iterations.

### 2. Running Tests in the Agent Loop

Always use `background=true, notify_on_complete=true`.

### 3. process wait with Too-Short Timeout

Set timeout generously (2-3x expected duration). There's no penalty for setting it high.

### 3b. `process(action="wait")` Timeout Clamping

`process(action="wait", timeout=N)` silently clamps to ~60s maximum. For long suites, use the fallback:

```
1. terminal("run-tests.sh", background=true, notify_on_complete=true, timeout=3600)
2. process(action="poll", session_id="...")   ← check status (sparse — 2-4 calls)
3. Read output from a log FILE: read_file("/tmp/test-output.log")
4. When process(action="poll") shows status="exited", read the final results.
```

Always redirect background output to a file: `"> /tmp/playwright-out.log 2>&1"`.

### 4. Using kanban_block Instead of process wait

**Fix:** Use `process(action="wait")` to stay in the same run. Blocking mid-work causes re-dispatch.

### 5. Not Using notify_on_complete

Always pair `background=true` with `notify_on_complete=true` for finite tasks.

### 6. Killing a Background Process Without Checking Expected Duration

Before killing ANY long-running background process, compute the expected duration:
- **Whisper transcription (CPU):** file duration × 3-5
- **Video download (yt-dlp):** file size / rate limit
- **Test suite:** check historical run time from CI logs

Only kill when elapsed > 2× expected duration with zero progress.

## Cron Alternative (Recurring Validation)

```bash
cronjob(
  action="create",
  schedule="every 30m",
  script="ci-run-tests.sh",
  no_agent=true
)
```

## max_runtime Guidelines

| Task type | Recommended max_runtime | Why |
|-----------|------------------------|-----|
| Install/setup | 120s | Package downloads can be slow |
| Single test file (background) | 300s | Includes server start + test |
| Full test suite (background) | 1800s | 30 min for large suites |
| Self-contained loop script | 3600s | Multi-step benchmark cycles |

## Verification Checklist

- [ ] No `terminal("... test ...")` calls WITHOUT `background=true`
- [ ] Every background test run has `notify_on_complete=true`
- [ ] `process(action="wait")` used instead of polling loops
- [ ] Test scripts output to a file for post-mortem reading
- [ ] `max_runtime_seconds` is 2-3x expected duration
- [ ] Multi-step loops use self-contained scripts (not inline iteration)
