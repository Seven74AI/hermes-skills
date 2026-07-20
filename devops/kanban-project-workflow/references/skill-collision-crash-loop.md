# Pitfall: Silent Crash Loop from Skill Collisions

## Symptom

Kanban worker tasks show `running` status but never make progress. Logs repeat the same error on every run: `Unknown skill(s): <name>`. No `blocked` state is reached, no notification fires even if `notify-subscribe` is configured on the task.

## Root Cause

A skill name has an ambiguous collision — two copies exist in the profile's skill directories (e.g., a Matt Pocock symlink in `skills/<name>/` AND a local copy in `skills/software-development/<name>/`). The skill resolver refuses to pick → worker crashes on startup.

The dispatcher treats this as a transient crash:

```
running → crash → crash → gave_up → promoted → running → crash → ...
```

- `gave_up` fires after `failure_limit` crashes (default: 2)
- `promoted` resets the counter and respawns
- If there's only one assignee (e.g., only `coder`), promotion is a no-op → infinite loop
- The task never reaches `blocked` status → notifications never fire

## Detection

```bash
# Check for consecutive crashes
hermes kanban --board <board> show <task_id> | grep -E "Diagnostics|consecutive_crashes"

# Check logs for repeated identical errors
hermes kanban --board <board> log <task_id> | tail -10
# Look for: "Unknown skill(s): <name>" repeating every ~60s
```

## Fix

1. Find the duplicate:
   ```bash
   find ~/.hermes/skills/ ~/.hermes/profiles/*/skills/ -path "*/software-development/<name>" -o -path "*/<name>/SKILL.md" 2>/dev/null
   ```

2. Identify which is the Matt Pocock original (symlink, fewer lines, no version frontmatter) and which is the local stub:
   ```bash
   file ~/.hermes/skills/<name>
   # symlink → Matt Pocock
   wc -l ~/.hermes/skills/<name>/SKILL.md ~/.hermes/skills/software-development/<name>/SKILL.md
   ```

3. Remove the non-Matt-Pocock copy from BOTH locations:
   ```bash
   rm -rf ~/.hermes/skills/software-development/<name>
   rm -rf ~/.hermes/profiles/coder/skills/software-development/<name>
   ```

4. Verify:
   ```bash
   hermes skills list | grep <name>
   # Should show exactly ONE entry
   ```

The worker picks up the fix on the next respawn cycle — no need to restart the dispatcher.

## Real Case

music-library board, 2026-07-08: tasks `t_11ca1f80` and `t_63cd171c` crashed 40+ times each over 40 minutes with `Unknown skill(s): tdd`. Two copies of `tdd` SKILL.md existed — the Matt Pocock symlink at `~/.hermes/skills/tdd/` and a stub at `~/.hermes/skills/software-development/tdd/` (and the same in `~/.hermes/profiles/coder/skills/`). The profile copy was the one the worker used, so removing only the global copy did not fix it. Both had to be removed.
