# Contradiction Check

Cross-reference pattern to detect drift between SOUL.md, profile config, kanban skill
recommendations, and per-ticket database settings.

## Why

SOUL.md is the worker's instruction manual. Config is the runtime enforcement. Skills are the
human operator's playbook. When these diverge, workers follow SOUL.md but get killed by config,
or tickets time out because the skill says 3600s but the DB says NULL.

## Checks to run

### 1. SOUL.md "90 turns" vs profile config max_turns

```bash
for p in coder reviewer researcher planner; do
  config_turns=$(python3 -c "import yaml;c=yaml.safe_load(open('/root/.hermes/profiles/$p/config.yaml'));print(c.get('agent',{}).get('max_turns','NOT SET'))")
  soul_mentions=$(grep -c '90 turns' "/root/.hermes/profiles/$p/SOUL.md" 2>/dev/null || echo 0)
  echo "$p: config=$config_turns SOUL_mentions_90=$soul_mentions"
done
```

Expected: config=90, soul_mentions_90>0 for all profiles.

### 2. max_iterations set on all profiles

```bash
for p in coder reviewer researcher planner; do
  val=$(python3 -c "import yaml;c=yaml.safe_load(open('/root/.hermes/profiles/$p/config.yaml'));print(c.get('agent',{}).get('max_iterations','MISSING'))")
  echo "$p: max_iterations=$val"
done
```

Expected: 120 on all (matches orchestrator skill recommendation).

### 3. Per-ticket max_runtime vs skill recommendation

Skill says 3600s for all tasks. Check DB:

```python
import sqlite3
for board in ['shop', 'the-swarm', 'videogame-lab', 'baguette', 'glance']:
    db = sqlite3.connect(f'/root/.hermes/kanban/boards/{board}/kanban.db')
    bad = db.execute(
        "SELECT COUNT(*) FROM tasks WHERE max_runtime_seconds IS NULL AND status IN ('todo','ready')"
    ).fetchone()[0]
    if bad:
        print(f'{board}: {bad} tasks with NULL runtime (will timeout at ~120s)')
    db.close()
```

### 4. max_spawn consistency

```bash
# Config value
python3 -c "import yaml;c=yaml.safe_load(open('/root/.hermes/config.yaml'));print('config:',c.get('kanban',{}).get('max_spawn','NOT SET (unlimited)'))"
# Check running workers
ps aux | grep 'hermes.*kanban' | grep -v grep | wc -l
```

If config says 5 but 20 workers are running: same-tick overspawn bug (see max-spawn-overspawn-bug.md).

### 5. SOUL.md stale references

```bash
# Old patterns that should no longer exist in SOUL
grep -rn 'npx vitest\|npx playwright\|npx tsc' /root/.hermes/profiles/*/SOUL.md && echo "STALE: npx references found"
grep -rn 'parent=task_id\|parent=coder_task' /root/.hermes/profiles/*/SOUL.md | grep -v 'NEVER\|WARNING' && echo "STALE: parent= pattern found"
grep -rnP '[\\x{1F300}-\\x{1F9FF}]' /root/.hermes/profiles/*/SOUL.md && echo "EMOJI: found in SOUL.md"
```

### 6. Ghost profile check (tickets assigned to deleted profiles)

```bash
EXISTING=$(hermes profile list 2>/dev/null | awk '/^  /{print $1}' | paste -sd '|')
for board in $(hermes kanban boards list 2>/dev/null | awk '/^  /{print $1}'); do
  hermes kanban --board "$board" list 2>/dev/null | while read -r line; do
    assignee=$(echo "$line" | awk '{print $NF}')
    status=$(echo "$line" | awk '{print $1}')
    [ "$status" = "done" ] && continue
    echo "$assignee" | grep -qE "^($EXISTING)$" || \
      echo "GHOST: $board $(echo $line | awk '{print $2}') -> $assignee"
  done
done
```

## When to run

- After any SOUL.md edit
- After profile creation/deletion
- After ticket decomposition (new tickets may have NULL runtime/body)
- Weekly as part of ops re-audit

## Real case

2026-05-20, 4 profiles + 12 boards. Found:
- max_spawn: memory said 3, config said 5 (config was updated, memory stale)
- max_iterations: 0 of 4 profiles had it set (skill recommends 120)
- 3 tickets with NULL runtime on the-swarm (would timeout at 120s)
- 5 tickets with NULL body (workers would have no spec)
- 0 emoji violations, 0 stale npx references, 0 ghost profiles

All fixed in <5 min. Without the check, 8 tasks would have failed on first dispatch.
