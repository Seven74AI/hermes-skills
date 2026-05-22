# Cron Audit Methodology

Systematic technique for auditing cron jobs — identifying waste, redundancy, and silent failures. Demonstrated 2026-05-21 during a scheduled cron review.

## Step 1 — List all jobs

```bash
hermes cron list --all
```

Note: `--all` includes paused jobs. The default list only shows active.

## Step 2 — For each suspect job, check session history

The session files reveal the actual behavior, not the intended design.

```python
import json, os, glob

sessions_dir = "/root/.hermes/sessions"
job_id = "4423bee366e6"  # example

files = sorted(glob.glob(f"{sessions_dir}/session_cron_{job_id}_*"))
print(f"Total sessions: {len(files)}")

# Analyze output patterns
silent = 0
verbose = 0
for fpath in files:
    with open(fpath) as f:
        session = json.load(f)
    for msg in reversed(session.get("messages", [])):
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
            if len(msg["content"]) <= 5:
                silent += 1
            else:
                verbose += 1
            break

print(f"Silent runs: {silent} ({silent/len(files)*100:.0f}%)")
print(f"Verbose runs: {verbose} ({verbose/len(files)*100:.0f}%)")
```

## Step 3 — Estimate token cost

LLM-driven cron jobs burn tokens even when silent — the system prompt, tool schema, and context are always processed.

**Rough estimation (for DeepSeek v4-pro):**
- System prompt + tools schema: ~10-12k tokens
- Context (watchdog output, previous results): 1-5k tokens  
- Total input per run: ~15k tokens
- Silent output: 5-10 tokens

```
daily_cost = runs_per_day × 15000 × input_price + runs_per_day × 10 × output_price
```

For 80 runs/day: ~1.2M input tokens. At DeepSeek pricing ≈ $0.20-0.50/day.
For 144 runs/day (every 10min): ~2.2M input tokens ≈ $0.40-0.90/day.

**When a cron job is 100% silent for >24h, it's wasting money.** Either reduce frequency, pause it, or delete it.

## Step 4 — Redundancy check

For each suspect cron, ask:
- Is there another cron covering the same territory? (e.g., midday-reflector vs nightly-reflector)
- Is there a native Hermes command that does this? (e.g., script-based GC vs `hermes kanban gc`)
- Is there a no-agent script that could do the same job for 0 tokens? (e.g., disk-watchdog.py vs Disk Cleanup Agent)
- Has it ever actually executed? (0 sessions = never ran = either broken or unneeded)

## Step 5 — Decision framework

| Signal | Action |
|--------|--------|
| 100% silent for >48h | **Delete** — not providing value |
| Redundant with another cron | **Delete** weaker one |
| Never executed (0 sessions) | **Decide**: run once manually to evaluate, or delete |
| Works but too frequent | **Reduce frequency** (e.g., every 10m → every 30m) |
| Script could replace agent | **Convert to no-agent** — eliminates token cost |
| Unique, useful, active | **Keep** — monitor periodically |

## Pitfalls

- **Don't trust the name.** The "Disk Cleanup Agent" hasn't cleaned anything in 210+ runs — the name describes intent, not behavior. Always check session data.
- **`context_from` can mask waste.** A watchdog→agent chain where the agent is always silent still consumes tokens. The agent is evaluating the context every time.
- **Count sessions, not scheduled runs.** Some jobs may be scheduled but the scheduler skips them (e.g., overlapping ticks, lock contention). Check actual session files.
- **Token costs accumulate silently.** A $0.002/run job at every 10min is $0.29/day = $8.70/month. Across multiple such jobs, this adds up.
- **The `cronjob` tool shows last-run status.** Use `hermes cron list` to see `Last run: ... ok` / `error` / empty — but "ok" doesn't mean "useful."
