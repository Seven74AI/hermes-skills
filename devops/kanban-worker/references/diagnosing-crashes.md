# Diagnosing Kanban Worker Crashes

When a kanban task shows `outcome: "crashed"` or `"pid not alive"`, the default retry diagnostic says "OOM or segfault — reduce memory footprint." That's insufficient. Follow this systematic diagnostic flow instead.

## Step 1: Check for skill name collisions (startup crashes — 60s death)

Workers that crash consistently in ~60s (startup window) with a mix of `pid X not alive` and `pid X exited with code 1` may have a **skill name collision**. This happens when a profile's skill directory contains a nested duplicate (e.g., `kanban-project-workflow/kanban-project-workflow/SKILL.md` alongside `kanban-project-workflow/SKILL.md`), typically from an rsync trailing-slash mistake.

**Detection:**
```bash
# Check for nested duplicate SKILL.md files
find /root/.hermes/profiles/<profile>/skills/ -mindepth 2 -name "SKILL.md" -path "*/*/SKILL.md" ! -path "*/references/*"

# Check error logs for collision warnings
tail -50 /root/.hermes/profiles/<profile>/logs/errors.log | grep "Skill name collision"
```

**Symptom confirmation:**
- `hermes kanban log <task>` shows "Error: Unknown skill(s): <name>" repeated
- `errors.log` shows `WARNING tools.skills_tool: Skill name collision for '<name>': 2 candidates`
- Every run dies at ~60s (startup time) — consistent crash timing
- `consecutive_crashes` climbs rapidly: 35+ in a few hours
- The skill appears in `hermes skills list` — confirming it exists in the main profile, just not loadable by the worker due to collision

**Fix:**
```bash
# Remove nested duplicate
rm -rf /root/.hermes/profiles/<profile>/skills/<category>/<skill-name>/<skill-name>/
# Reclaim crashed tasks
hermes kanban --board <board> reclaim <task_id>
```

**Root cause:** `rsync -a --delete source/ target` (no trailing slash on target) copies the source directory INSIDE target instead of merging contents. Always use trailing slashes on BOTH: `rsync -a --delete source/ target/`.

See `kanban-project-workflow` skill → "Pitfall: Nested duplicate skill directory from rsync" for full diagnosis and prevention.

## Step 2: Check the systemd journal

The OOM killer leaves a clear trace in the journal:

```bash
journalctl -u hermes-gateway --no-pager --since "HH:MM" --until "HH:MM"
```

Look for these smoking guns:
- `"A process of this unit has been killed by the OOM killer"` — definitive OOM
- `"Failed with result 'oom-kill'"` — gateway restart due to OOM
- `"Killing process PID (hermes) with signal SIGKILL"` — children killed by systemd cleanup
- `"Consumed X.XG memory peak, 0B memory swap peak"` — shows peak usage and swap situation

## Step 3: Check SWAP

Many VMs/containers ship with 0 swap:

```bash
free -h
swapon --show
```

If swap is 0B, the Linux OOM killer has no buffer — any memory spike kills processes. Even 2-4 GiB of swap gives enough headroom for multiple concurrent workers.

Quick fix:
```bash
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
```

## Step 4: Check available RAM and concurrent workers

```bash
free -h
hermes gateway status  # shows all running worker PIDs
```

Multiple hermes workers + npm/node/tsc subprocesses + MCP servers can easily exceed 7-8 GiB total. The gateway alone may consume 5 GiB at peak.

## Step 5: Check if gateway restarted during the task window

Gateway restarts kill all child workers. If the restart counter increments during the task run, the worker was collateral damage, not the cause:

```
May 17 23:44:36 systemd: Scheduled restart job, restart counter is at 1.
May 17 23:54:36 systemd: Scheduled restart job, restart counter is at 2.
```

If the crash timestamp matches a restart, the task itself may be fine — it just got killed mid-work.

## Step 6: Check task runtime vs max-runtime

Some tasks simply need more time. Check the task's `max_runtime_seconds` vs actual runtime. Increase with `--max-runtime 30m` if needed.

## Step 7: Check for API provider credit exhaustion (HTTP 402)

When workers exit cleanly (rc=0) but the diagnostics show `repeated_crashes: worker exited cleanly (rc=0) without calling kanban_complete or kanban_block — protocol violation`, the root cause may be the API provider returning HTTP 402 (Insufficient Balance). This is NOT a crash — the worker process exits normally because the LLM API call fails immediately, so it never gets to make any tool calls (kanban_complete, kanban_block, or even a heartbeat).

**Symptom pattern:**
- All workers on ALL boards crash simultaneously (not just one board)
- Diagnostics show `consecutive_crashes=N` climbing rapidly
- `journalctl -u hermes-gateway | grep "HTTP 402"` shows `Insuficient Balance`
- Workers exit with rc=0 (clean exit, not a signal kill)
- No OOM-killer trace in journal
- Cron jobs also fail with same 402 error

**Confirm:**
```bash
journalctl -u hermes-gateway --since "2 hours ago" --no-pager | grep -i "HTTP 402\|Insufficient Balance"
```

**Recovery:**
```bash
# 1. Replenish API credits first (user action)

# 2. Reclaim all running tasks to break the crash loop
for board in $(hermes kanban boards list 2>/dev/null | awk '/^  /{print $1}'); do
  hermes kanban --board "$board" list --status running 2>/dev/null | grep '●' | awk '{print $2}' | while read tid; do
    hermes kanban --board "$board" reclaim "$tid"
  done
done

# 3. Verify workers restart cleanly
hermes kanban --board <board> list --status running
```

**Why rc=0 (protocol violation) instead of a crash:** The worker process starts, tries to call the LLM API, gets HTTP 402 on the very first request, and the framework exits normally — it never reaches the point of calling any kanban tool. The dispatcher sees a clean exit without protocol completion and re-spawns, creating a tight crash loop.

## Common root causes (ranked by frequency)

1. **Skill name collision (nested duplicate skill directory)** — 60s startup death, "Unknown skill(s)" error, 35+ consecutive crashes
2. **No swap on memory-constrained host** — gateway + 3-4 workers OOM-kill
3. **Gateway restart cascade** — one worker OOMs, gateway dies, kills all others
4. **API provider credit exhaustion (HTTP 402)** — all workers fail simultaneously, rc=0 "protocol violation" (see Step 7)
5. **Task too long for default runtime** — needs `--max-runtime` increase
6. **Actual code bug causing infinite loop / memory leak** — rarest but check logs

## Anti-pattern: jumping to "split the task"

Splitting tasks should be the LAST resort, not the first. A task that works in 10 minutes end-to-end shouldn't be split into 4 sub-tasks just because the host has no swap. Fix the environment first, then consider splitting only if the task genuinely needs more than ~20 minutes of agent context.
