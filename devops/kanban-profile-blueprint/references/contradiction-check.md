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

Expected:
- coder: config=180 (intentional 2× override), SOUL may say 90 or 180
- All other standard profiles (reviewer, researcher, planner): config=90, soul_mentions_90>0
- Specialty profiles (edgee-planner, hermes-devops, twitter-coder): config=90+
- researcher-videos: config=240

### 2. agent.max_turns set correctly on all profiles

The ONLY key that controls iteration budget is `agent.max_turns` (default 90).
`agent.max_iterations` is a DEAD KEY — never consumed by any code path.
Root-level `max_turns` and `max_iterations` are also dead (legacy leftovers ignored
when `agent.max_turns` is present).

```bash
for p in coder reviewer researcher planner edgee-planner hermes-devops twitter-coder; do
  val=$(python3 -c "
import yaml, sys
with open('/root/.hermes/profiles/$p/config.yaml') as f:
    c = yaml.safe_load(f)
    agent = c.get('agent', {})
    # The key that matters
    print(agent.get('max_turns', 'MISSING'))
" 2>/dev/null)
  echo "$p: agent.max_turns=$val"
done
```

Expected:
- `coder`: 180 (2× default for complex multi-file changes)
- All others: 90 or higher
- If 90 and workers exhaust budget → bump to 120–180 using `hermes config set --profile <name> agent.max_turns <value>`.

Also check for dead root-level keys that should be removed:

```bash
for p in coder reviewer researcher planner edgee-planner hermes-devops twitter-coder; do
  has_root_max_turns=$(python3 -c "
import yaml
with open('/root/.hermes/profiles/$p/config.yaml') as f:
    c = yaml.safe_load(f)
print('YES' if 'max_turns' in c and not isinstance(c.get('agent', {}), dict) else
      'YES' if 'max_turns' in c and 'max_turns' not in c.get('agent', {}) else 'NO')
" 2>/dev/null)
  has_root_max_iter=$(python3 -c "
import yaml
with open('/root/.hermes/profiles/$p/config.yaml') as f:
    c = yaml.safe_load(f)
print('YES' if 'max_iterations' in c and 'max_iterations' not in c.get('agent', {}) else 'NO')
" 2>/dev/null)
  [ "$has_root_max_turns" = "YES" ] && echo "  DEAD KEY: $p has root-level max_turns (ignored — remove it)"
  [ "$has_root_max_iter" = "YES" ] && echo "  DEAD KEY: $p has root-level max_iterations (ignored — remove it)"
done
```

Root-level `max_turns` is only used as a legacy fallback when `agent.max_turns` is missing
(see normalization in `hermes_cli/config.py:_normalize_max_turns_config()`).
Root-level `max_iterations` is never consumed at all.

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

### 6. SOUL.md review handoff has promote step

The kanban dispatcher only picks up `ready` tasks, but `kanban_create()` creates tasks in `todo`. Any SOUL.md that has a "Review Handoff" section MUST include explicit promotion of the reviewer task. Without it, the reviewer rots in `todo` forever — deadlock.

```bash
# Profiles with review handoff sections that are MISSING the promote step
for p in coder hermes-devops twitter-coder; do
  has_review=$(grep -c "Review Handoff" "/root/.hermes/profiles/$p/SOUL.md" 2>/dev/null || echo 0)
  has_promote=$(grep -c "promote.*review" "/root/.hermes/profiles/$p/SOUL.md" 2>/dev/null || echo 0)
  if [ "$has_review" -gt 0 ] && [ "$has_promote" -eq 0 ]; then
    echo "MISSING PROMOTE: $p has Review Handoff but NO promote step → deadlock risk"
  fi
done
```

Expected: every profile with a Review Handoff section must return `has_promote > 0`.

### 7. SOUL.md block-vs-complete contradiction

A SOUL.md that has BOTH a "Review Handoff" section (which instructs the worker to `kanban_block(reason="review-required")`) AND a "Completion" / "TERMINATE" section (which instructs the worker to `kanban_complete()`) contains contradictory termination instructions. The worker can't both block AND complete — it must pick one, and the ambiguity causes protocol violations.

```bash
# Profiles with both review handoff AND completion/terminate sections
for p in coder hermes-devops twitter-coder reviewer; do
  has_block=$(grep -c "review-required" "/root/.hermes/profiles/$p/SOUL.md" 2>/dev/null || echo 0)
  has_complete=$(grep -c "kanban_complete" "/root/.hermes/profiles/$p/SOUL.md" 2>/dev/null || echo 0)
  if [ "$has_block" -gt 0 ] && [ "$has_complete" -gt 0 ]; then
    echo "CONTRADICTION: $p — both review-required block ($has_block refs) AND kanban_complete ($has_complete refs)"
  fi
done
```

Expected: profiles with review handoff should either (a) have NO `kanban_complete` in their termination path, or (b) clearly disambiguate in the Completion section between review-requiring tasks (→ block) and non-review tasks (→ complete). A profile that says both with no disambiguation is ambiguous.

Fix pattern: for profiles where ALL tasks require review (e.g., twitter-coder), replace the Completion section with a note that the worker should NEVER call `kanban_complete`. For profiles where some tasks require review and some don't (e.g., hermes-devops), add conditional language to the Completion section.

**Real case (2026-07-06):** Audit of 8 active profiles found hermes-devops and twitter-coder both had block-vs-complete contradictions. Both were patched. The root cause was the `templates/devops-soul.md` template — also patched.

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
