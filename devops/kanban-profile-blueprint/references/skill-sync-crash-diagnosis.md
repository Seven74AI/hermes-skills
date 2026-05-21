# Skill Sync Crash Diagnosis

Full diagnosis recipe for "Unknown skill(s): X" crashes on kanban workers
that other workers on the same board handle fine.

## Symptom

One task crashes repeatedly (`exit code 1`, "Unknown skill(s): X"), while
other tasks on the same board with the same skills list work fine.

## Root Cause

The `.skills_prompt_snapshot.json` cache masks a missing skill directory.
The snapshot was generated when the skill WAS present, so all subsequent
worker spawns reuse the cached snapshot. A specific task triggers snapshot
regeneration → the real filesystem scan fails → crash.

## Diagnosis Recipe

### 1. Get the task's skills list

```bash
hermes kanban --board <board> show <task_id> | grep "skills:"
# e.g. "skills: shop, github-code-review"
```

### 2. Check which profiles have the skill on disk

```bash
for profile in coder edgee-planner hermes-devops planner researcher reviewer twitter-coder; do
  if [ -d "/root/.hermes/profiles/$profile/skills/dogfood/shop" ]; then
    echo "✅ $profile"
  else
    echo "❌ $profile"
  fi
done
```

### 3. Check the .skills_prompt_snapshot.json

```bash
python3 -c "
import json
with open('/root/.hermes/profiles/<profile>/.skills_prompt_snapshot.json') as f:
    d = json.load(f)
shop = [s for s in d['skills'] if 'shop' in s.get('skill_name','').lower()]
print(f'Skill in snapshot: {len(shop)}')
"
```

### 4. Check session cache vs reality

Query the profile's state.db to see if sessions loaded the skill:

```python
import sqlite3, time
db = sqlite3.connect('/root/.hermes/profiles/<profile>/state.db')
db.row_factory = sqlite3.Row

# Sessions that loaded the skill
rows = db.execute("""
    SELECT id, started_at, message_count,
           LENGTH(system_prompt) as sp_len
    FROM sessions
    WHERE system_prompt LIKE '%<skill_name>%'
    ORDER BY started_at DESC
    LIMIT 20
""").fetchall()

for r in rows:
    ts = time.strftime('%m-%d %H:%M', time.localtime(r['started_at']))
    print(f"  {ts} | msgs:{r['message_count']:>4} | sp_len:{r['sp_len']}")
```

**Key diagnostic:** if ALL sessions have the same `sp_len` (e.g. 21288 bytes),
the snapshot is cached. If sessions have different prompt sizes at different
times, the snapshot is being regenerated.

### 5. Check if crashed task created any session

```python
crashes = db.execute("""
    SELECT COUNT(*) as n FROM sessions
    WHERE system_prompt LIKE '%<skill_name>%'
    AND message_count < 3
""").fetchone()
print(f"Crash sessions (msgs<3): {crashes['n']}")
```

Zero crash sessions in state.db despite 176+ kanban runs = process dies before
session creation (bootstrap failure during skill loading).

## Recovery

```bash
# 1. Copy the skill to the affected profile(s)
cp -r /root/.hermes/skills/dogfood/<skill> \
      /root/.hermes/profiles/<profile>/skills/dogfood/<skill>

# 2. Release the crashed task's claim
hermes kanban --board <board> reassign <task_id> <assignee> --reclaim

# 3. Trigger fresh dispatch
hermes kanban --board <board> dispatch

# 4. Wait ~90s, verify no new crashes
hermes kanban --board <board> diagnostics | grep <task_id>
```

## Prevention

After any skill update, sync to ALL profiles:

```bash
for p in coder reviewer researcher planner edgee-planner hermes-devops twitter-coder; do
  mkdir -p "/root/.hermes/profiles/$p/skills/dogfood/<skill>"
  cp /root/.hermes/skills/dogfood/<skill>/SKILL.md \
     "/root/.hermes/profiles/$p/skills/dogfood/<skill>/SKILL.md"
  echo "$p: OK"
done
```

## Real Case: shop/reviewer (2026-05-20)

- `t_fe9ad8a7` (Review: Sentry replay PII masking audit) crashed 176× with
  "Unknown skill(s): shop"
- 26 OTHER reviewer sessions loaded shop successfully during the same period
  (all using identical 21288-byte cached snapshot)
- The `shop` directory existed in 6 of 7 profiles; missing from `reviewer`
- State.db showed zero sessions with <3 messages for the crashed task
  (bootstrap failure, no session record)
- Curator and sync-script were cleared (neither touches profile skills)
- Fix: `cp` + `reassign --reclaim` + `dispatch` → session created with 42 msgs
