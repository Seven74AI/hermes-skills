# Diagnosing Kanban Worker Crashes

When a kanban task shows `outcome: "crashed"` or `"pid not alive"`, the default retry diagnostic says "OOM or segfault — reduce memory footprint." That's insufficient. Follow this systematic diagnostic flow instead.

## Step 1: Check the systemd journal

The OOM killer leaves a clear trace in the journal:

```bash
journalctl -u hermes-gateway --no-pager --since "HH:MM" --until "HH:MM"
```

Look for these smoking guns:
- `"A process of this unit has been killed by the OOM killer"` — definitive OOM
- `"Failed with result 'oom-kill'"` — gateway restart due to OOM
- `"Killing process PID (hermes) with signal SIGKILL"` — children killed by systemd cleanup
- `"Consumed X.XG memory peak, 0B memory swap peak"` — shows peak usage and swap situation

## Step 2: Check SWAP

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

## Step 3: Check available RAM and concurrent workers

```bash
free -h
hermes gateway status  # shows all running worker PIDs
```

Multiple hermes workers + npm/node/tsc subprocesses + MCP servers can easily exceed 7-8 GiB total. The gateway alone may consume 5 GiB at peak.

## Step 4: Check if gateway restarted during the task window

Gateway restarts kill all child workers. If the restart counter increments during the task run, the worker was collateral damage, not the cause:

```
May 17 23:44:36 systemd: Scheduled restart job, restart counter is at 1.
May 17 23:54:36 systemd: Scheduled restart job, restart counter is at 2.
```

If the crash timestamp matches a restart, the task itself may be fine — it just got killed mid-work.

## Step 5: Check task runtime vs max-runtime

Some tasks simply need more time. Check the task's `max_runtime_seconds` vs actual runtime. Increase with `--max-runtime 30m` if needed.

## Common root causes (ranked by frequency)

1. **No swap on memory-constrained host** — gateway + 3-4 workers OOM-kill
2. **Gateway restart cascade** — one worker OOMs, gateway dies, kills all others
3. **Task too long for default runtime** — needs `--max-runtime` increase
4. **Actual code bug causing infinite loop / memory leak** — rarest but check logs

## Anti-pattern: jumping to "split the task"

Splitting tasks should be the LAST resort, not the first. A task that works in 10 minutes end-to-end shouldn't be split into 4 sub-tasks just because the host has no swap. Fix the environment first, then consider splitting only if the task genuinely needs more than ~20 minutes of agent context.
