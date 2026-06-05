# Kanban Dispatcher Tick Failure Pattern

## Symptom

Repeated errors in gateway logs:
```
gateway.run: kanban dispatcher: tick failed on board <board_name>
```

- Only one board affected (others dispatch normally)
- No stack trace, no crash — silent recurring failure
- Gateway stays up, other platforms (Telegram, Discord) unaffected
- Workers stop receiving tasks for that board

## Real-World Case: shop board (2026-05-24 → 2026-06-04)

- 68 occurrences over 11 days before detection
- Board had 532 tasks, all idle (0 in_progress)
- Root cause not yet diagnosed (suspected DB corruption or orphaned task state)

## Quick Diagnosis

```bash
# 1. Count occurrences
grep -c "kanban dispatcher.*tick failed on board <board>" /root/.hermes/logs/errors.log

# 2. Check first occurrence (how long has this been going on?)
grep "kanban dispatcher.*tick failed on board <board>" /root/.hermes/logs/errors.log | head -1

# 3. Check board DB integrity
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
cur = conn.cursor()
cur.execute('PRAGMA integrity_check')
print(cur.fetchone()[0])
cur.execute('SELECT status, COUNT(*) FROM tasks GROUP BY status')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')
"

# 4. Compare with a working board's schema
for board in <board> the-swarm; do
  echo "=== $board ==="
  sqlite3 /root/.hermes/kanban/boards/$board/kanban.db ".schema" 2>/dev/null
done
```

## Detection Gap

The existing watchdogs (kanban-block, kanban-integrity) do NOT detect dispatcher tick failures:
- **kanban-block**: scans for blocked/crash-looping tasks — doesn't catch dispatch failures
- **kanban-integrity**: checks DB structure — won't flag a board that simply can't be ticked
- **CI watchdog**: monitors CI pipelines, not kanban dispatch health

A "dispatcher health" watchdog that alerts when a board fails N consecutive ticks would close this gap.
