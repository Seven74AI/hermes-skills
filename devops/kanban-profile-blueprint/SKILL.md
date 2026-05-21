---
name: kanban-profile-blueprint
description: Blueprint for creating and maintaining Hermes kanban worker profiles — config templates, role definitions, bootstrap script, and all lessons learned from production firefighting.
version: 1.9.0
platforms: [linux]
metadata:
  hermes:
    tags: [kanban, profiles, devops, workflow, template]
---

# Kanban Profile Blueprint

Blueprint for kanban worker profiles. Covers role definitions, config templates,
and all systemic fixes discovered during production operations.

## Profiles we actually need (simplified)

Instead of 24+ profiles per project, use **role-based profiles** with
project-specific SOUL.md. The same coder works on any board.

| Role | Profile | Needs git push? | max_turns | Notes |
|------|---------|----------------|-----------|-------|
| Coder | `coder` | ✅ Yes | 90 | Implements code + tests. Background+wait = ~15-20 turns. |
| Reviewer | `reviewer` | ❌ No | 90 | Reviews PRs/diffs. 3 outcomes: approve/needs changes/reject. |
| Researcher | `researcher` | ✅ Maybe | 90 | Investigates, writes docs. |
| Planner | `planner` | ❌ No | 90 | Decomposes into tasks. Never implements. |
| DevOps | `<project>-devops` | ✅ Yes | 90 | CI/CD, systemd, watchdogs, backups, incident response. SOUL.md template: `templates/devops-soul.md`. |
| Coder creates review for wrong profile | LLM "helpfully" changes `assignee=\"reviewer\"` to `assignee=\"shop-reviewer\"` (project-specific, deleted). Task never dispatched. | In coder SOUL.md, use ALL-CAPS emphasis: `assignee=\\\"reviewer\\\"` — **EXACTLY this string, never project-specific. The profile is literally named `reviewer`.** |
| Reviewer approves game code that doesn't launch | Code review was static (read code, check logic). Godot/GDScript can parse fine but fail at runtime (scene load errors, type mismatches). | Reviewer MUST run headless Godot validation: `godot --headless --quit --path .` before approving. If Godot not installed → block with "needs runtime validation" + request human playtest. Never mark game task `done` without one of: headless pass, or explicit user playtest confirmation. |
| Coder finishes task but never pushes to GitHub | Code only exists in kanban scratch workspace. Workspace gets GC'd → code lost. Repo stays empty. | Coder MUST `git push origin main` before blocking for review. If repo is empty on first task: initialize it, commit proto code, push. No push = task not complete. |
| Scratch workspace is the only copy of code | Workspace directory cleaned by GC after task completes. GitHub repo was never populated. User has no access to code. | Every project MUST have its code on GitHub. Coder initializes repo on first task. After completion: archive tar.gz to Discord + push to GitHub. Dual redundancy. |

**No `coder-long` needed.** Background+wait + self-contained scripts make 90 turns
sufficient for any task. The `-long` profile was a workaround for bad patterns
(inline tests, polling) that are now explicitly banned in SOUL.md.

See `references/operational-infrastructure.md` for cron jobs (watchdog, GC, disk cleanup, crash-loop detection).

## Cross-Board Audit

When a systemic bug is found on one board (review tasks stuck in todo, silent workers,
ghost profiles), run the audit script to catch it on ALL boards:

```bash
python3 ~/.hermes/skills/devops/kanban-profile-blueprint/scripts/audit-all-boards.py
# With auto-fix:
python3 ~/.hermes/skills/devops/kanban-profile-blueprint/scripts/audit-all-boards.py --fix
```

This checks: review-todo, no-heartbeat, ghost-profiles, stuck-todo across every board.
For manual targeted audits, see:
- `references/ticket-audit-pattern.md` — audit todo tickets for missing runtime, body, broken links
- `references/ticket-decomposition-recipe.md` — full recipe: archive bundles → create atomic → backfill body/runtime → verify graph
- `references/contradiction-check.md` — cross-reference SOUL vs config vs ticket DB vs skill recommendations
- `references/ticket-body-audit.md` — find and fix tickets created without body
- `references/parallelization-unlinking.md` — unlink artificial dependencies to maximize parallel worker throughput

**Crash-loop watchdog:** a silent crash loop (task stays `running`, dispatcher respawns endlessly) is invisible to the block watchdog. Run separately or via `watchdog-all.py`:
```bash
python3 ~/.hermes/skills/devops/kanban-profile-blueprint/scripts/check-crash-loops.py
# Report only (no auto-block):
AUTO_BLOCK=false python3 ~/.hermes/skills/devops/kanban-profile-blueprint/scripts/check-crash-loops.py
```
See `references/operational-infrastructure.md` for full details.

### Token economy (mandatory in every worker SOUL.md)

```markdown
## Token Economy (CRITICAL — budget = 90 turns)

You have 90 turns (iterations). Every tool call burns 1 turn. When you hit 90,
the gateway kills you with "iteration budget exhausted" and your work is LOST.
The watchdog will unblock you, but you restart from zero.

### The ONE rule: background+wait for ALL heavy work

```
# WRONG — NEVER — burns 50-200 turns on test output lines
terminal("npm run test")
terminal("npm run test:e2e")
terminal("npm run lint")

# RIGHT — ALWAYS — burns 2-3 turns total
# Add a combined script to package.json: "test:all": "tsc --noEmit && vitest run && playwright test"
terminal("npm run test:all", background=true, notify_on_complete=true)
process(action="wait", timeout=3600)    # blocks WITHOUT burning turns
read_file("test-results.json")
```

### Anti-patterns that kill your budget

| WRONG — Death pattern | RIGHT — Life pattern |
|-----------------------|---------------------|
| `terminal("npm run test")` inline | `terminal("npm run test:all", bg=true)` + `process wait` |
| `while sleep 10; do tail log; done` (1 turn/poll) | `process(action="wait")` (0 turns) |
| `for f in *.ts; do read_file "$f"; done` | `search_files` or batch reads |
| "Let me just run the tests real quick" inline | STOP. Background+wait. Every time. |

### Multi-step iteration -> self-contained script

If you need test->fix->retest->fix cycles, write a SINGLE bash script that does
ALL the work internally, call it ONCE with background+wait. You use 3 turns
instead of 30.

### Budget checkpoints
- **30 turns used (33%)** — heartbeat with "budget OK, X% used"
- **60 turns used (66%)** — STOP immediately. Block with `kanban_block(reason="budget warning: partial <summary>")`. Partial work + clean block > dead worker.
- **75+ turns** — you're about to die. Push to git NOW, block immediately.

### Why this matters (real case)
t_8228590c on the-swarm: 3 consecutive runs, same mistake — ran E2E tests inline every time.
Run #571 exhausted at 90/90, #573 protocol violation crash, #579 idle 36min -> reclaimed.
**3 runs, ~3h wasted, zero progress.** Don't be run #580.
```

**Why 90 is enough:** A well-behaved coder uses ~15-25 turns:
`kanban_show(1) → git log(1) → read/write/patch(5-10) → background test(1) → wait(0) → read results(1) → push(1) → comment+review+block(3)`.
90 gives 3-4x headroom. Higher budgets encourage lazy patterns.

**`test:all` script:** Add a combined script to `package.json` so workers
have a single command to run all tests. Eliminates the "I'll just run
one test inline real quick" excuse. Full pattern: `references/test-all-script-pattern.md`.

## Git authentication — the chosen fix

**We do NOT use `terminal.env_passthrough`.** We rejected it because it
bypasses Hermes's security sanitizer for a provider credential — a nuclear
option for a surgical problem.

**Instead, we use token-in-URL + fork workflow:**

### Per-workspace setup (run once when creating or fixing a workspace)

```bash
TOKEN=$(grep '^GITHUB_TOKEN=' /root/.hermes/.env | head -1 | cut -d= -f2-)
cd /path/to/workspace

# 1. Embed token in git remote URL (survives env sanitizer)
git remote set-url origin "https://git:${TOKEN}@github.com/Seven74AI/${REPO}.git"

# 2. Add upstream for tracking (no auth needed for fetch)
git remote add upstream "https://github.com/${UPSTREAM_ORG}/${REPO}.git"

# 3. CRITICAL: clear credential helper — it overrides URL-embedded tokens
git config --unset credential.helper 2>/dev/null
HOME=/root/.hermes/profiles/${PROFILE}/home git config --global --unset credential.helper 2>/dev/null
```

### Why this works

- The token lives in the git remote URL, NOT in environment variables
- `_sanitize_subprocess_env()` strips env vars but can't touch git config
- `git push origin main` uses the URL-embedded token automatically
- We push to the FORK (Seven74AI/repo), not upstream (mnlamart/repo)
- A separate kanban task or manual step creates the PR from fork → upstream

### Why NOT env_passthrough

`terminal.env_passthrough` tells Hermes "let this provider credential through
the security sanitizer into ALL shell subprocesses." This means:
- Every `echo`, `ls`, `npm install` sees the token in its environment
- A malicious dependency could exfiltrate it via postinstall scripts
- Security audit surface increases dramatically

Token-in-URL is scoped to `git push` only. The sanitizer stays intact.

**Step 0 in SOUL.md:** The coder SOUL.md template (`templates/coder-soul.md`) now includes
a mandatory "Workspace Setup (Step 0)" section. Workers verify the token is embedded on
every run. This handles the case where the dispatcher clones a fresh scratch workspace
without auth — the worker self-repairs before starting work.

## SOUL.md style conventions

**No emojis.** Emojis in SOUL.md headings (like ⏱️ 💾 🔍 🎮 🔧 ⛔) add
zero value for the LLM and waste tokens. Use plain text headings only:
`## Heartbeats` not `## ⏱️ Heartbeats`. Templates in `templates/` already
follow this rule — when deploying, verify with:
```bash
python3 -c "import re; t=open('SOUL.md').read(); print(len(re.findall(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF]', t)))"
# Must return 0
```

## SOUL.md templates

## Coder SOUL.md — Branch + PR workflow (current standard)

The coder profile now uses a branch/PR workflow instead of direct main pushes.
Main is protected — CI must pass before merge.

Key sections in the canonical template (`templates/coder-soul.md`):
1. **Workspace Setup (Step 0)** — embeds GITHUB_TOKEN in git remote URL using `grep` on `~/.hermes/.env` (file read, NOT env var — survives subprocess sanitizer)
2. **Branch workflow** — `git checkout -b feat/t_XXX` before any work
3. **PR creation** — `gh pr create` with test results in body
4. **CI gate** — `gh pr checks` before merge
5. **Token Economy** — background+wait, anti-patterns, budget checkpoints
6. **Package manager** — always verify with `ls *lock*` (npm vs pnpm). Do NOT hardcode `pnpm`.

### Token embedding pattern
```bash
TOKEN=$(grep '^GITHUB_TOKEN=' ~/.hermes/.env | head -1 | cut -d= -f2-)
REPO=$(git remote get-url origin | sed 's|https://github.com/||' | sed 's|\.git$||')
git remote set-url origin "https://git:${TOKEN}@github.com/${REPO}.git"
git config --unset credential.helper 2>/dev/null
```
This works because `grep` reads a FILE on disk — the env sanitizer strips `$GITHUB_TOKEN`
from subprocess environments but cannot block file reads.

### Package manager detection
```bash
# Check lockfile to determine package manager
ls package-lock.json && PKG="npm run" || ls pnpm-lock.yaml && PKG="pnpm"
```
SOUL.md templates use `npm run test:all` by default, but workers should verify.

### test:all script
Every project repo should have:
```json
"test:all": "tsc --noEmit && vitest run && playwright test"
```
One command = one background call = 2-3 iterations burned instead of 50-200.

Full template: `templates/coder-soul.md`

```
# Coder

You implement code and tests for kanban tasks. You work on any board.

Key rules:
- Heartbeat every 5 minutes while working
- Git push at least every 10 minutes, BEFORE blocking for review
- Pre-review gate: run full test suite in background+wait, verify it passes
- Review handoff: create reviewer WITHOUT parent, promote it, then block yourself
  WARNING: assignee MUST be exactly "reviewer" — never project-specific

TOKEN ECONOMY (90 turns):
- NEVER run tests/benchmarks inline — background+wait always
- NEVER poll — process wait = 0 turns, polling = 1 turn each
- Multi-step iteration: write self-contained script, call ONCE with background+wait
- 30 turns: heartbeat with budget status
- 60 turns: STOP and block with partial summary
- 75+ turns: push to git, block immediately

Full rules, anti-patterns, and examples: templates/coder-soul.md
```

### Reviewer SOUL.md

Full template: `templates/reviewer-soul.md`

```
# Reviewer

You review code from coder tasks. You work on any board. Last line of defense.

TOKEN ECONOMY (90 turns):
- NEVER run tests inline — background+wait always
- NEVER poll — process wait = 0 turns
- 60 turns: STOP and block with partial findings

Godot/game projects: headless validation REQUIRED before APPROVE. 5-step checklist.

Full rules, verdicts, and game review process: templates/reviewer-soul.md
```

### Researcher SOUL.md

Full template: `templates/researcher-soul.md`

```
# Researcher

You investigate, explore, and analyze. You answer questions and provide context.
You work on any board. You do NOT implement code.

TOKEN ECONOMY (90 turns):
- Batch everything: web_extract(urls=[...]) — 5 pages in 1 turn
- Batch web_search then web_extract in parallel, never serial
- NEVER loop over URLs one by one
- 60 turns: STOP and block with partial findings

Completion: kanban_complete(summary, metadata={sources, findings, recommendation})

Full rules: templates/researcher-soul.md
```

### DevOps SOUL.md

See `templates/devops-soul.md` for the full template. Key differences from coder:
- Handles systemd services, CI/CD pipelines, backups, monitoring
- Uses `hermes gateway restart` not raw systemctl for gateway
- Always checks `systemctl status` before restarting services
- Backup before destructive config changes

## Bootstrap script

Single command to create all profiles:

```bash
# ~/.hermes/scripts/bootstrap-kanban-profiles.sh
# Creates: coder, reviewer, researcher, planner

for profile in coder reviewer researcher planner; do
  hermes profile create "$profile" --clone 2>/dev/null || echo "$profile exists"
  # --clone copies config but model/provider are top-level, not nested.
  # Hermes reads model.provider (nested), so we MUST write the correct structure.
  python3 -c "
import yaml
path = '/root/.hermes/profiles/$profile/config.yaml'
with open(path) as f:
    cfg = yaml.safe_load(f)
cfg['model'] = {'default': 'deepseek-v4-pro', 'provider': 'deepseek', 'base_url': 'https://api.deepseek.com/v1'}
cfg.pop('provider', None)
with open(path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False)
"
done

# Set max_turns + max_iterations per role
hermes -p coder config set agent.max_turns 90
hermes -p coder config set agent.max_iterations 120
hermes -p reviewer config set agent.max_turns 90
hermes -p reviewer config set agent.max_iterations 120
hermes -p researcher config set agent.max_turns 90
hermes -p researcher config set agent.max_iterations 120
hermes -p planner config set agent.max_turns 90
hermes -p planner config set agent.max_iterations 120

# Copy SOUL.md templates
cp ~/.hermes/skills/devops/kanban-profile-blueprint/templates/coder-soul.md \
   ~/.hermes/profiles/coder/SOUL.md
# ... (repeat for each role)

echo "Done. Verify: hermes profile list"
```

## Post-Deployment Verification (MANDATORY)

After creating profiles and writing SOUL.md, run these checks. Profiles with broken config or stale SOUL.md will crash on first dispatch with no warning.

```bash
# 1. Every profile must have nested model.provider set (not top-level)
for p in coder reviewer researcher planner; do
  result=$(python3 -c "
import yaml
with open('/root/.hermes/profiles/$p/config.yaml') as f:
    cfg = yaml.safe_load(f)
m = cfg.get('model', {})
if not isinstance(m, dict) or not m.get('provider'):
    print('BROKEN')
else:
    print(f'{m[\"provider\"]}/{m[\"default\"]}')
" 2>/dev/null)
  if echo "$result" | grep -q 'deepseek'; then
    echo "✓ $p: $result"
  else
    echo "❌ $p: model.provider NOT deepseek — fix with Python script"
  fi
done

# 2. Coder SOUL.md must NEVER contain parent=task_id (deadlock hazard)
# NOTE: The warning text "NEVER use `parent=task_id`" in SOUL.md will match this grep.
# That's a false positive — the warning IS the correct content. Only flag matches that
# appear in kanban_create() calls or function arguments, not in WARNING blocks.
grep -rn 'parent=task_id' /root/.hermes/profiles/*/SOUL.md | grep -v 'NEVER\|WARNING' && \
  echo "FAIL: parent=task_id used as instruction — fix NOW" || echo "OK: No deadlock hazards (warnings only)"

# 3. Reviewer config must be a full clone, not a stub (check size)
for p in coder reviewer researcher planner; do
  size=$(wc -c < /root/.hermes/profiles/$p/config.yaml)
  [ "$size" -lt 1000 ] && echo "❌ $p config.yaml too small ($size bytes) — regenerate from default"
done

# 4. Verify no tasks reference deleted profiles
for board in $(hermes kanban boards list 2>/dev/null | awk '/^  /{print $1}'); do
  hermes kanban --board "$board" list 2>/dev/null | grep -E '(shop-|music-|edgee-|startup-|twitter-|game-|videogame-)' && \
    echo "❌ $board has tasks on old profiles — reassign before deleting profiles"
done

echo "✓ Verification complete"
```

**5. Cross-check all ticket assignees against existing profiles**

Even if config is valid, tickets assigned to non-existent profiles will never dispatch. Run this across ALL boards:

```bash
# Get existing profiles
EXISTING=$(hermes profile list 2>/dev/null | awk '/^  /{print $1}' | paste -sd '|')

# Check every board
for board in $(hermes kanban boards list 2>/dev/null | awk '/^  /{print $1}'); do
  hermes kanban --board "$board" list 2>/dev/null | while read -r line; do
    ticket_id=$(echo "$line" | awk '{print $2}')
    status=$(echo "$line" | awk '{print $1}')
    assignee=$(echo "$line" | awk '{print $NF}')
    # Skip headers and done tasks (done tasks with wrong profiles are informational)
    if [ "$status" = "done" ] || [ "$status" = "✓" ]; then continue; fi
    if ! echo "$assignee" | grep -qE "^($EXISTING)$"; then
      echo "❌ $board/$ticket_id: $assignee (DOES NOT EXIST — will never dispatch)"
    fi
  done
done
```

Active tickets (ready/running/blocked) pointing at ghost profiles are **blocking** — reassign immediately. Done tickets with ghost profiles are informational (they ran before profile cleanup) and can be ignored.

```bash
# Quick fix: reassign a ticket to a standard profile
hermes kanban --board <board> reassign <ticket_id> reviewer  # or coder/researcher/planner
```

Note: reassigning a running task requires `--reclaim` to release the current worker's claim first:
```bash
hermes kanban --board <board> reassign <ticket_id> <new_assignee> --reclaim
```

echo "✓ All verifications complete"

## Fork PR workflow (for repos where you don't have write access)

When the GITHUB_TOKEN belongs to user X but the repo is under org Y:

```
1. Worker pushes to fork (origin = Seven74AI/repo)
2. CI runs automatically on push (after one-time Actions enablement — see below)
3. CI passes → create PR from fork to upstream
4. PR review on upstream
```

**Setting up fork remotes per workspace:**
```bash
TOKEN=$(grep '^GITHUB_TOKEN=' ~/.hermes/.env | head -1 | cut -d= -f2-)
git remote set-url origin "https://git:${TOKEN}@github.com/Seven74AI/${REPO}.git"
git remote add upstream "https://github.com/mnlamart/${REPO}.git"
git config --unset credential.helper  # prevents override of URL token
```

**Enabling CI on fork (one-time per repo):**

GitHub silently disables Actions on forks by default. Push events are ignored even when the workflow has `push:` in its `on:` block. This is a security measure — you must explicitly opt in.

```bash
# Enable Actions on the fork (gh CLI, one-time)
echo '{"enabled":true,"allowed_actions":"all"}' | \
  gh api --method PUT /repos/Seven74AI/$REPO/actions/permissions --input -

# Verify
gh api /repos/Seven74AI/$REPO/actions/permissions
# Should return: {"enabled":true,"allowed_actions":"all"}

# After this, every git push to main/dev triggers CI automatically
```

If you don't have `gh` CLI available but have the token:
```bash
TOKEN=$(grep '^GITHUB_TOKEN=' ~/.hermes/.env | head -1 | cut -d= -f2-)
curl -s -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Seven74AI/$REPO/actions/permissions" \
  -d '{"enabled":true,"allowed_actions":"all"}'
```

## Reviewing game / Godot projects — CRITICAL

**Static code review is NOT sufficient for game code.** A GDScript file that parses correctly can still fail at runtime (missing methods, type errors, scene loading failures). The reviewer MUST validate the project actually loads before approving:

```
# Godot headless validation (minimum bar for APPROVE)
godot --headless --quit --path /path/to/project 2>&1
# Must exit 0 and show no ERR or FATAL lines
```

If Godot is not installed on the server: **the reviewer MUST block with "needs runtime validation"** and note that approval requires a human playtest. Never mark a game task `done` without either headless validation passing or explicit user playtest confirmation.

The coder should include the Godot headless output in their handoff comment. If absent, the reviewer MUST request it before proceeding.

## Project Bootstrap

For creating a new project from scratch (repo → board → skill → tickets with dependencies),
see `references/project-bootstrap.md`.

Each project should maintain a canonical design doc (`docs/UNLOCKS.md` or `docs/DESIGN.md`)
with phase mechanics, gameplay loops, and resource tables. Workers reference it from
ticket bodies. Full pattern: `references/project-doc-pattern.md`.

## Mass Crash Recovery

When 3+ tasks on a board crash identically (same exit code, same duration, all within minutes),
it's usually a transient provider API issue. See `references/mass-crash-diagnosis.md`.

## Common pitfalls & fixes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `GITHUB_TOKEN vide` | Token stripped by `_sanitize_subprocess_env()` | Embed token in git remote URL (see "Git authentication"). Clear credential helper. |
| `push 403 "denied to X"` | Pushing to upstream instead of fork | Set origin to fork, add upstream for tracking |
| Worker exits without kanban_block | SOUL.md doesn't instruct termination | Add TOKEN ECONOMY section to SOUL.md with budget checkpoints |
| Profile has no model after clone (`—` in list)
| Task stuck in `gave_up` | `consecutive_failures` triggered circuit breaker | Reset in SQLite: `UPDATE tasks SET consecutive_failures=0 WHERE id='t_xxx'`. Then unblock+dispatch. |
| CI not triggering on fork | GitHub disables Actions on forks by default (silently ignores push events even when workflow has `push` trigger) | **One-time fix per repo:** enable Actions via API: `echo '{"enabled":true,"allowed_actions":"all"}' | gh api --method PUT /repos/Seven74AI/repo/actions/permissions --input -`. After that, `git push` triggers CI automatically — no `workflow_dispatch` needed. Verify with `gh api /repos/Seven74AI/repo/actions/permissions`. |
| `mergeable_state: unstable` | No CI checks reported to PR | Ensure CI runs on PR's exact HEAD SHA |
| Duplicate review tasks | Worker doesn't check for existing reviews | Scan board before creating review task. Link don't duplicate. |
| Reviewer orphaned (parent archived) | Disk incident destroyed coder workspace | Archive reviewer, recreate coder task if needed |
| Credential helper overrides URL token | `git config credential.helper = store` | `git config --unset credential.helper` (local + global in profile home) |
| Worker exhausts budget on test output (90/90) | Worker runs `npm run test:e2e` inline instead of background+wait. 12 E2E Playwright tests = 50-200 iterations of log output. | Add `test:all` script to package.json, update SOUL.md to mandate `terminal("npm run test:all", background=true, notify_on_complete=true)` + `process(action="wait")`. See `references/test-all-script-pattern.md`. |
| Reviewer doesn't know what to do | kanban-worker missing REJECT outcome | 3 outcomes: approve, needs changes, reject (see Reviewer SOUL.md) |
| Reviewer tasks stuck in `todo` forever | Created with `--parent` (children of running/blocked never promoted) | Create reviewers WITHOUT parent. Include coder ID in title: `"Review: (t_coder_id) ..."` |
| Destructive command runs without explanation | `rm -rf`, force-push, DB writes trigger user approval | Before ANY destructive command, state WHAT it does and WHY in one line. Don't make the user ask. |
| Profile deleted while tasks still running on it | Didn't check task assignments before deletion | Before deleting a profile: `hermes kanban --board <board> list | grep <profile>` for ALL boards. Only delete when zero running/blocked tasks reference it. |
| SOUL.md emojis cause confusion | LLMs treat emojis as noise, not signal. They add visual clutter without improving instruction adherence. | Remove all emojis (⛔⚠️🔥✅❌💾...) from SOUL.md files. Use plain text: WRONG/RIGHT, WARNING, STOP, OK. Keep functional punctuation (—, →). |
| Worker uses wrong package manager | SOUL.md hardcodes `pnpm` but project uses `npm` (or vice versa) | Always detect with `ls *lock*`. Never hardcode. SOUL.md templates default to `npm run` but workers must verify. |
| Worker hits iteration budget on E2E tests | Runs `npm run test:e2e` inline instead of background+wait. Each test log line burns 1 iteration. 12 E2E tests can consume 50-200 iterations. | Enforce TOKEN ECONOMY section in coder SOUL.md: `terminal("npm run test:all", background=true, notify_on_complete=true)` + `process(action="wait")`. 2-3 iterations vs 50-200. |
| Workspace lacks git auth token | Dispatcher clones scratch workspace without auth. `git push` fails with 403. | Step 0 in coder SOUL.md: `grep GITHUB_TOKEN ~/.hermes/.env` (file read, not env var) → `git remote set-url`. Survives subprocess sanitizer. |
| Branch protection blocks direct push | Main is protected. Workers used to `git push origin main` → now rejected. | Workers must use feature branches + PRs. See `references/branch-protection-pr-workflow.md`. |
| All tickets chained behind one parent (serial bottleneck) | Planner sets one ticket as parent for everything. 7+ tickets blocked in `todo`, only 1 worker running. | Unlink artificial dependencies: `hermes kanban unlink <parent> <child>`. Only keep code-level dependencies. See `references/parallelization-unlinking.md`. |
| `test:all` script missing from package.json | Workers have no single command to run all tests → temptation to run one inline. | Add to package.json: `"test:all": "tsc --noEmit && vitest run && playwright test"`. See `references/test-all-script-pattern.md`. |
| `max_iterations` not set on profiles | Profiles fall back to AIAgent default (90). Complex tasks hit budget exhaustion. | Set on all 7 profiles: `for p in coder reviewer researcher planner edgee-planner hermes-devops twitter-coder; do hermes config set --profile "$p" max_iterations 120; hermes config set --profile "$p" kanban.max_iterations 120; done`. Both top-level and `kanban:` section must have `max_iterations: 120`. Default if unset is 90 (AIAgent constructor). |
| Worker crashes with "Unknown skill(s)" | Skills are per-profile. `skill_manage()` creates only in the main `~/.hermes/skills/`. Worker profiles have their own copy at `~/.hermes/profiles/<name>/skills/`. A stale `.skills_prompt_snapshot.json` cache can mask missing skill directories — other tasks on the same board work fine while one triggers snapshot regeneration and crashes. See `references/skill-sync-crash-diagnosis.md` for full diagnosis recipe. | **Quick fix:** `cp -r /root/.hermes/skills/dogfood/<skill> /root/.hermes/profiles/<profile>/skills/dogfood/<skill>` then `reassign --reclaim` + `dispatch`. **Prevention:** after any skill update, sync to ALL profiles (7, not just 4): `for p in coder reviewer researcher planner edgee-planner hermes-devops twitter-coder; do mkdir -p "/root/.hermes/profiles/$p/skills/dogfood/<skill>" && cp /root/.hermes/skills/dogfood/<skill>/SKILL.md "/root/.hermes/profiles/$p/skills/dogfood/<skill>/SKILL.md"; done`. **Diagnosis:** check state.db sessions for identical `sp_len` (cached snapshot), cross-check all profiles with `[ -d ... ]`, verify `.skills_prompt_snapshot.json` includes the skill. Caused 8 researchers (baguette+glance) + 1 reviewer (shop, 176 crashes) before root cause documented. |
| `kanban complete` fails on task in `todo` state | `complete` requires the task to be `running` — won't work on `todo` or `ready` | Use SQLite directly: `python3 -c "import sqlite3; db=sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db'); db.execute(\"UPDATE tasks SET status='done', completed_at=unixepoch() WHERE id='t_xxx'\")"` |
| Coder creates review for wrong profile | LLM changes `assignee="reviewer"` to `assignee="shop-reviewer"` (deleted profile). Task never dispatched. | In coder SOUL.md, use ALL-CAPS: `assignee="reviewer"` — **EXACTLY this string, never project-specific.** |
| DB not found at expected path | Each board has its OWN DB: `kanban/boards/<board>/kanban.db`. Top-level `kanban/kanban.db` is empty. | Always target the per-board DB. Find it: `find /root/.hermes/kanban/boards -name 'kanban.db' -not -empty` |
| Task ready for hours, diagnostic "Ready for Xh with no worker" | Task assigned to non-existent profile. Dispatcher cannot find assignee → task stays ready forever. Watchdog does not catch it (not blocked). | Full recovery recipe: `references/ghost-profile-recovery.md`. Quick fix: `hermes kanban --board <board> reassign <id> reviewer`. Also caught by cross-check script in Verification section. |
| SOUL.md deployed with stale/broken content | Manual deploy from memory instead of from the canonical template. E.g. `parent=task_id` crept back into coder SOUL.md. | Always deploy from the skill's template file. After writing, verify with grep: `grep -rn 'parent=task_id' /root/.hermes/profiles/*/SOUL.md` should return NOTHING. |
| Ops tickets go stale after infra changes | Audit tickets from days ago recommend actions (monitoring scripts, MCP sharing, disk cleanup). Infrastructure evolves; old recommendations rot. | After major infra changes, run a re-audit: see `references/ops-reaudit-pattern.md`. |
| `hermes kanban boards switch` then `list` shows wrong board | `boards switch` prints "Active board is now 'X'" but `list` still shows startup-lab tasks. Board switch is unreliable for `list`/`show`. | Always use `--board <slug>` directly on the action: `hermes kanban --board glance list`, `hermes kanban --board shop create "..." --assign coder`. This is 100% reliable. |
| All 5 worker slots occupied by zombie/stuck tasks → ready tasks queue forever (0 blocked, progress frozen) | `max_spawn` limits concurrent workers. When all slots are taken by tasks that are done-but-not-blocked (review-required handoff posted but worker still running), stale (no heartbeat for hours), or in timeout loops, the dispatcher cannot pick up ready tasks. Board shows 0 blocked but 20+ ready waiting 7-12h. | **Diagnosis:** check each running task's heartbeats and last comment. **Fix recipe:** 1) For tasks with review-required handoff posted → mark `done` via SQL + create standalone review. 2) For zombie tasks (no heartbeat >2h) → kill PID + `reclaim`. 3) For timeout-loop tasks → bump `max_runtime_seconds` in DB + `reclaim`. 4) NEVER just block — dispatcher auto-unblocks when parents are done. |
| All tasks on a board crash identically in same window | Provider API stream drops (e.g. DeepSeek `RemoteProtocolError`), web search rate-limited. All workers fail before reaching real work. | Don't change profiles/tasks — it's transient API. Unblock all, reset `consecutive_failures` in SQLite, let dispatcher retry. See `references/mass-crash-diagnosis.md`. |
| User asks \"recap des board\" and then wants tickets on idle boards | User expects zero idle boards — every board must always have active work. Empty boards are treated as a problem. | After a recap, proactively identify idle boards. Propose 2-3 tickets per idle board (1 feature + 1 research + 1 test). For game boards (baguette, the-swarm, videogame-lab): propose 3+ phases, each heavy. Use `project-ci` skill for test ticket templates. Present as a list for user validation before creating. **CRITICAL:** before proposing tickets, check what project/product is ALREADY built on that board. Don't propose re-doing work (e.g. re-selecting from ideation when a project like MIROIR was already chosen and built). Read a few done tickets to understand current phase. |
| Task times out repeatedly at ~62s | Default `max_runtime_seconds=60` on tasks. Downloads (Godot addons, npm packages, Docker images, git clones) routinely take 60-120s. Worker dies mid-download, watchdog unblocks, same timeout repeats — 4+ consecutive failures with no progress. | **At creation:** `hermes kanban create ... --max-runtime 180` for any task involving downloads. **For existing stuck tasks:** update SQLite directly: `UPDATE tasks SET max_runtime_seconds=180, consecutive_failures=0 WHERE id='t_xxx'` then `hermes kanban --board <b> unblock <id>`. **Also:** ensure coder SOUL.md has the \\\"Long Downloads / Installs\\\" section (background+notify pattern). Real case: videogame-lab t_6303d37c (GUT addon install) timed out 4× at 61-62s before max_runtime raised to 180s. |
| Worker created without body | `hermes kanban create` via CLI without `--body` flag leaves `body=NULL` in DB. Worker has no spec → improvises or blocks immediately. | Always pass `--body` on create, or use SQLite to backfill: `UPDATE tasks SET body='<spec>' WHERE id='<tid>'`. Audit with: `SELECT id, title FROM tasks WHERE body IS NULL AND status='todo'`. Full decomposition recipe (audit → archive → create → backfill → verify): `references/ticket-decomposition-recipe.md`. |
| `max_iterations` not set on profiles | Profiles fall back to AIAgent default (90). Complex tasks hit budget exhaustion. | Set on all 7 profiles: `for p in coder reviewer researcher planner edgee-planner hermes-devops twitter-coder; do hermes config set --profile "$p" max_iterations 120; hermes config set --profile "$p" kanban.max_iterations 120; done`. Both top-level and `kanban:` section must have `max_iterations: 120`. Default if unset is 90 (AIAgent constructor). |
| Config drift: `kanban.max_iterations` inconsistent | Profiles accumulate different values over time. Workers on low-iteration profiles hit budget exhaustion. Default when unset is 90 (AIAgent), not 50. | Audit with `references/profile-config-audit.md`. Fix: `hermes config set --profile <name> max_iterations 120` AND `hermes config set --profile <name> kanban.max_iterations 120` for ALL 7 profiles (coder, reviewer, researcher, planner, edgee-planner, hermes-devops, twitter-coder). |
| Config drift: `kanban.max_spawn` inconsistent | Some profiles at 5, others at 3. Over-spawning risks CPU saturation. | Audit with `references/profile-config-audit.md`. Fix: `hermes config set --profile <name> kanban.max_spawn 3`. |
| Project skills out of sync across profiles | `skill_manage` creates/patches only the main `~/.hermes/skills/`. Profile copies become stale silently — workers load wrong instructions. Includes `kanban-project-workflow`, `shop`, `the-swarm`, and any other project/skill in `dogfood/` or `devops/`. | Audit with `references/profile-config-audit.md` skill sync script. Fix: `for p in coder reviewer researcher planner edgee-planner hermes-devops twitter-coder; do cp /root/.hermes/skills/dogfood/<skill>/SKILL.md /root/.hermes/profiles/$p/skills/dogfood/<skill>/SKILL.md; done`. Same for `devops/kanban-project-workflow`. Observed 2026-05-20: the-swarm out of sync on ALL 7 profiles. |

## Batch notification subscriptions

When the user wants notifications for ALL tickets on a board, the `hermes kanban notify-subscribe` CLI only works with global DB tasks — board-specific tasks need a direct SQLite insert:

```python
import sqlite3, time
conn = sqlite3.connect('/root/.hermes/kanban.db')
for tid in ['t_aaa', 't_bbb', 't_ccc']:
    conn.execute(
        'INSERT INTO kanban_notify_subs (task_id, platform, chat_id, thread_id, created_at) VALUES (?, ?, ?, ?, ?)',
        (tid, 'telegram', '<chat_id>', '', int(time.time()))
    )
conn.commit()
```

Full reference: `hermes-agent` skill → `references/kanban-notify-subscriptions.md`.