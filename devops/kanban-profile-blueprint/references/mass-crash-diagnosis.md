# Mass Crash Diagnosis

When multiple tasks on the same board (or multiple boards) crash identically in the same time window, treat it as a systemic failure — not per-task bugs.

## Recognition signals

- 3+ tasks on the same board crash within 2 minutes of each other
- Identical exit codes (e.g., all `exit_code: 1`)
- Identical run durations (e.g., all ~60s)
- The crash happens during the first few turns (workers never reach real work)
- `kanban show` on any of them shows `exit_kind: nonzero_exit` with no useful error

## Diagnostic flow

1. **Check run events** for one task: `hermes kanban --board <board> show <task_id>` — look at the timeline
2. **Try manual reproduction**: Run one task manually to see the actual error output
   ```bash
   timeout 120 hermes -p <profile> --skills kanban-worker chat -q "work kanban task <task_id>" 2>&1 | tail -50
   ```
3. **Look for API-level errors** in the output, not kanban-level errors:
   - `RemoteProtocolError` / `stream drop` — provider API instability
   - `rate-limited` / `[error]` on web_search — backend throttling
   - `Interrupted during API call` — process killed mid-call (likely timeout or API hang)
4. **Check if the provider is working NOW**: you're chatting with it — if it works, the blip passed

## Common root causes

| Symptom | Cause | Verification |
|---|---|---|
| All workers crash at 60s, `RemoteProtocolError` | Provider API stream drops (DeepSeek unstable) | Check if your own chat is stable |
| `search 0.6s [error]` | Web search backend rate-limited | Try web_search manually |
| `Interrupted during API call` | Process killed by timeout | Check task `max_runtime` and gateway timeout |

## Remediation (batch)

When it's a transient API blip (provider unstable, now stable):

```bash
# 1. Unblock all affected tasks
for board in baguette glance; do
  for tid in $(hermes kanban --board "$board" list --status blocked 2>/dev/null | awk '/⊘/{print $2}'); do
    hermes kanban --board "$board" unblock "$tid"
  done
done

# 2. Reset consecutive_failures to 0 (so they don't re-block on one more crash)
python3 -c "
import sqlite3
for board, tids in [
    ('baguette', ['t_xxx', 't_yyy']),
    ('glance', ['t_aaa', 't_bbb']),
]:
    db = sqlite3.connect(f'/root/.hermes/kanban/boards/{board}/kanban.db')
    for tid in tids:
        db.execute(\"UPDATE tasks SET consecutive_failures=0 WHERE id=?\", (tid,))
    db.commit()
    print(f'✓ {board}: reset')
"
```

# 3. Let the dispatcher retry (interval: 60s)
```

**Do NOT** change profile config, SOUL.md, or task bodies for transient API issues. The worker code is fine — the provider had a hiccup.

**Do NOT cargo-cult config changes without root cause.** When tasks crash, resist the urge to change `max_spawn`, `failure_limit`, or other kanban configs before you've proven the cause. Example: 2026-05-19, 8 researchers crashed with exit code 1. We reduced `max_spawn` from 5 to 3 thinking concurrency was the issue. Real root cause: missing project skills in worker profiles (skills are per-profile). The config change was noise; the crash pattern was identical before and after. Verify with manual reproduction before touching config.

## When to escalate

If crashes persist after 2 retry cycles (unblock → crash → unblock → crash):
- Provider may be down or rate-limiting your account
- Check provider status page
- Consider switching the researcher profile to a different provider temporarily
- Block with `reason="Provider unstable: deepseek stream drops — <provider> status?"` — human decision needed
