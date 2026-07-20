# Dispatcher Stuck — Rapid Diagnosis

When the user asks "why only N workers running?" or "pourquoi le board n'avance pas?", follow this path.

## Symptom

- `hermes kanban list` shows `ready=N` with few/no `running` tasks
- `ps aux | grep hermes.*kanban` confirms < max_spawn workers
- Gateway logs show: `kanban dispatcher stuck: ready queue non-empty for N consecutive ticks but 0 workers spawned`

## Diagnostic path (4 commands — run in order)

```bash
# 1. Confirm the stuck pattern
grep 'dispatcher stuck\|spawned=0' ~/.hermes/logs/gateway.log | tail -10

# 2. Check for skill collisions (FIRST — most common, produces no worker logs)
for skill in $(ls -d ~/.hermes/profiles/coder/skills/*/ 2>/dev/null); do
  name=$(basename "$skill")
  [ -d ~/.hermes/skills/*/"$name" ] 2>/dev/null && echo "⚠️  COLLISION: $name in coder profile"
done

# 3. Check for missing skills (worker crash signature)
grep 'Unknown skill' ~/.hermes/kanban/boards/<board>/logs/t_*.log 2>/dev/null | tail -5

# 4. Check for DB integrity issues (last — rarest actual cause)
grep 'not a valid SQLite database\|disabling dispatch' ~/.hermes/logs/errors.log | tail -10
```

## Root cause identification

### A. Skill collision in worker profile (MOST COMMON — CHECK FIRST)

**Fingerprint:** Dispatcher stuck with "0 workers spawned" despite ready tasks. No DB corruption errors in logs. `consecutive_failures` on ready tasks may be 0 (dispatcher stopped spawning before tasks failed).

**Two variants:**

**Variant 1 — Missing skill:** `--skill` flag references a skill that doesn't exist in `/root/.hermes/profiles/<profile>/skills/`. Worker logs show `Error: Unknown skill(s): <name>`. Fix: copy the skill to the profile.

**Variant 2 — Skill name collision (the silent killer):** A skill with the same bare name exists in BOTH `~/.hermes/skills/` AND `~/.hermes/profiles/<profile>/skills/`. Hermes can't resolve which one to load — workers crash on startup with `Unknown skill(s): <name>` before producing any log output. The dispatcher counts these as spawn failures, hits `failure_limit`, and stops spawning completely. **This produces NO worker logs** — the crash happens before the worker writes anything. The `grep 'Unknown skill'` diagnostic will return empty even though the problem IS skills.

**Diagnose variant 2 (collision):**
```bash
# Find skills that exist in both the global dir and the profile dir
for d in ~/.hermes/profiles/<profile>/skills/*/; do
  skill=$(basename "$d")
  [ -d ~/.hermes/skills/*/"$skill" ] 2>/dev/null && echo "⚠️  COLLISION: $skill"
done
```

**Fix variant 2:**
```bash
# Remove the stale copy from the profile (keep the global one)
rm -rf ~/.hermes/profiles/<profile>/skills/<category>/<skill-name>
# Gateway restart may be needed to clear stuck dispatcher state
systemctl restart hermes-gateway
```

**Real case (2026-07-13):** `grill-with-docs` existed in both `~/.hermes/skills/software-development/` and `~/.hermes/profiles/coder/skills/software-development/` (profile copy was the older/stale one). Dispatcher stuck for 4+ hours spawning 0 workers despite `max_spawn=3` and 5 ready tasks. Manual worker spawns also produced 0 output. Removing the profile copy + gateway restart resolved it. The WAL corruption theory was incorrectly applied first — user debunked it as having been debunked 3 times previously.

**⛔ When the user says "read the logs" or points at a specific data source, GO THERE FIRST.** Do not theorize, do not run diagnostic commands, do not search elsewhere — go directly to the file/log/source the user is pointing at. In this session, the user said "Ba lit les logs c'est qui dit que c'est pas reconnu" — the watchdog's session output literally said "unknown block type" and "Watchdog classification gap," but the agent was searching errors.log instead of reading the watchdog's own session output. The answer was in the data the user pointed to.

### A2. Respawn guard (active_pr) blocks spawn — dispatcher stuck with 0 spawned

**Fingerprint:** Same as skill collision — dispatcher stuck, 0 workers spawned. But the root cause is `respawn_guarded` events on ready tasks, visible via:

```bash
sqlite3 ~/.hermes/kanban/boards/<board>/kanban.db \
  "SELECT task_id, substr(payload,1,80), datetime(created_at,'unixepoch','localtime')
   FROM task_events WHERE kind='respawn_guarded' ORDER BY created_at DESC LIMIT 10;"
```

**Cause:** Tasks have GitHub PR URLs in their `task_comments`. The dispatcher's `check_respawn_guard` scans comments for PR URLs within 24h (`_RESPAWN_GUARD_PR_WINDOW = 86400`). When found, it sets `active_pr` guard and skips spawning. This happens even when the reviewer has already approved — the guard doesn't check review status.

**Typical scenario:** Coder creates PR → posts handoff comment with full PR URL (violating the "PR #N only" rule in `kanban-project-workflow`) → blocks for review → reviewer approves → task unblocked → dispatcher sees `active_pr` guard → 0 workers spawned for 24h.

**Fix:**
```bash
sqlite3 ~/.hermes/kanban/boards/<board>/kanban.db \
  "DELETE FROM task_comments WHERE body LIKE '%github.com%pull%';"
```
Tasks become spawnable on the next dispatcher tick.

**Prevention:** See `kanban-project-workflow` § "⛔ NEVER include the PR URL in comment" and `kanban-orchestrator` § Step 3 "Coder tasks MUST include kanban-project-workflow in skills."

**Real case (2026-07-13):** 5 ready coder tasks all showed `respawn_guarded` with reason `active_pr`. Each had a "review-required handoff" comment containing a `github.com/.../pull/` URL. Reviewers had all completed (done ✓) but the 24h guard blocked spawn. Deleting the PR URL comments allowed the dispatcher to spawn within one tick.

### B. DB integrity issues (rare — check second)

**Fingerprint:** `kanban dispatcher: board <board> database ... is not a valid SQLite database; disabling dispatch` in errors.log. The dispatcher disables the board and re-enables when the DB fingerprint changes. This produces a stuck/unstuck cycle (spawned=1 → stuck → spawned=1). The root cause is NOT long gateway uptime — that theory has been debunked multiple times. Check DB integrity directly: `sqlite3 <db> "PRAGMA integrity_check"`.

**Fix:** `systemctl restart hermes-gateway`. If the board doesn't recover, check `references/kanban-db-corruption-recovery.md`.

### C. Profile health (rare)

**Fingerprint:** No DB corruption, no skill errors, but dispatcher stuck anyway.

Check: `hermes profile list` — is the gateway column `running` or `stopped` for the target profile? If stopped, workers can't spawn through that profile's gateway.

## Quick recovery (after fixing root cause)

After fixing the root cause (skill collision removed, DB repaired, etc.), the dispatcher may still be stuck. A gateway restart clears the stuck state:

```bash
systemctl restart hermes-gateway
```

Then wait 1-2 minutes for the dispatcher to start claiming tasks. Verify with `hermes kanban list`.
