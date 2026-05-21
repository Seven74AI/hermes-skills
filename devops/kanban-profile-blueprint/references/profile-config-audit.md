# Profile Config Consistency Audit

Every profile should have the same kanban config keys with the same values.
Drift happens over time — manual edits, bootstrap omissions, or profile-specific
experiments that never got reverted. This audit catches it.

## What to check

| Key | Expected | Why |
|-----|----------|-----|
| `kanban.max_iterations` | 120 | Workers with lower values hit "iteration budget exhausted" on complex tasks |
| `kanban.max_spawn` | 3 | Higher values risk CPU saturation on shared hosts |
| `kanban.failure_limit` | 3 | Consistent circuit breaker threshold |
| `kanban.dispatch_in_gateway` | true | All profiles dispatch from the gateway |
| `kanban.dispatch_interval_seconds` | 60 | Consistent dispatch timing |

## Verification script

```bash
#!/bin/bash
# Audit all profiles for kanban config consistency
# Usage: bash profile-config-audit.sh

PROFILES_DIR="/root/.hermes/profiles"
EXPECTED_MAX_ITER=120
EXPECTED_MAX_SPAWN=3

echo "=== Profile Config Audit ==="
issues=0

for p in $(ls "$PROFILES_DIR"); do
    config="$PROFILES_DIR/$p/config.yaml"
    [ ! -f "$config" ] && continue

    # Extract kanban section values
    kanban_max_iter=$(python3 -c "
import yaml
with open('$config') as f:
    cfg = yaml.safe_load(f)
k = cfg.get('kanban', {})
print(k.get('max_iterations', 'NOT SET'))
" 2>/dev/null)

    kanban_max_spawn=$(python3 -c "
import yaml
with open('$config') as f:
    cfg = yaml.safe_load(f)
k = cfg.get('kanban', {})
print(k.get('max_spawn', 'NOT SET'))
" 2>/dev/null)

    if [ "$kanban_max_iter" != "$EXPECTED_MAX_ITER" ]; then
        echo "  $p: max_iterations=$kanban_max_iter (expected $EXPECTED_MAX_ITER)"
        issues=$((issues + 1))
    fi

    if [ "$kanban_max_spawn" != "$EXPECTED_MAX_SPAWN" ]; then
        echo "  $p: max_spawn=$kanban_max_spawn (expected $EXPECTED_MAX_SPAWN)"
        issues=$((issues + 1))
    fi
done

if [ "$issues" -eq 0 ]; then
    echo "  All profiles consistent."
else
    echo "  $issues issue(s) found. Fix with:"
    echo "  hermes config set --profile <name> kanban.max_iterations 120"
    echo "  hermes config set --profile <name> kanban.max_spawn 3"
fi
```

## Skill sync verification

Project skills live in the main `~/.hermes/skills/dogfood/<project>/SKILL.md`.
Each profile has its own copy at `~/.hermes/profiles/<name>/skills/dogfood/<project>/SKILL.md`.
Workers load the profile copy — if it's stale, they operate with wrong instructions.

```bash
#!/bin/bash
# Audit skill sync across profiles
# Usage: bash skill-sync-audit.sh

SKILLS_DIR="/root/.hermes/skills/dogfood"
PROFILES_DIR="/root/.hermes/profiles"

echo "=== Skill Sync Audit ==="

for skill_dir in $(ls "$SKILLS_DIR"); do
    main="$SKILLS_DIR/$skill_dir/SKILL.md"
    [ ! -f "$main" ] && continue
    main_hash=$(md5sum "$main" | cut -d' ' -f1)

    out_of_sync=""
    for p in $(ls "$PROFILES_DIR"); do
        profile_skill="$PROFILES_DIR/$p/skills/dogfood/$skill_dir/SKILL.md"
        if [ ! -f "$profile_skill" ]; then
            out_of_sync="$out_of_sync $p:MISSING"
        else
            phash=$(md5sum "$profile_skill" | cut -d' ' -f1)
            if [ "$phash" != "$main_hash" ]; then
                out_of_sync="$out_of_sync $p:MISMATCH"
            fi
        fi
    done

    if [ -n "$out_of_sync" ]; then
        echo "  $skill_dir:$out_of_sync"
    else
        echo "  $skill_dir: OK (all profiles synced)"
    fi
done
```

## Quick fix — sync one skill to all profiles

```bash
SKILL=the-swarm  # or shop, music-library, etc.
for p in coder reviewer researcher planner edgee-planner hermes-devops twitter-coder; do
    mkdir -p "/root/.hermes/profiles/$p/skills/dogfood/$SKILL"
    cp "/root/.hermes/skills/dogfood/$SKILL/SKILL.md" \
       "/root/.hermes/profiles/$p/skills/dogfood/$SKILL/SKILL.md"
    echo "$p: synced"
done
```

## When to run

- After any skill update (`skill_manage` action on a project skill)
- After profile creation or modification
- After the weekly curator consolidates skills
- Proactively: weekly, or whenever a worker crashes with "Unknown skill(s)"
