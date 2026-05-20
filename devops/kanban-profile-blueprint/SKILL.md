---
name: kanban-profile-blueprint
description: Blueprint for creating and maintaining Hermes kanban worker profiles — config templates, role definitions, bootstrap script, and all lessons learned from production firefighting.
version: 1.4.0
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

See `references/operational-infrastructure.md` for cron jobs (watchdog, GC, disk cleanup).

## Cross-Board Audit

When a systemic bug is found on one board (review tasks stuck in todo, silent workers,
ghost profiles), run the audit script to catch it on ALL boards:

```bash
python3 ~/.hermes/skills/devops/kanban-profile-blueprint/scripts/audit-all-boards.py
# With auto-fix:
python3 ~/.hermes/skills/devops/kanban-profile-blueprint/scripts/audit-all-boards.py --fix
```

This checks: review-todo, no-heartbeat, ghost-profiles, stuck-todo across every board.

### Token economy (mandatory in every worker SOUL.md)

```markdown
## TOKEN ECONOMY (CRITICAL — budget = 90 turns)
- NEVER run tests/benchmarks inline. Always: terminal(bg=true, notify_on_complete=true) + process(action="wait").
- Polling loops = instant budget death. One `process wait` replaces 50-100 turns.
- If >60 turns used (66%) → STOP immediately and block with "budget warning: partial <summary>".
  Partial work + clean block > complete work + crash.
- Multi-step iteration: use a self-contained script. Worker calls it ONCE in background.
```

**Why 90 is enough:** A well-behaved coder uses ~15-25 turns:
`kanban_show(1) → git log(1) → read/write/patch(5-10) → background test(1) → wait(0) → read results(1) → push(1) → comment+review+block(3)`.
90 gives 3-4x headroom. Higher budgets encourage lazy patterns.

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

## SOUL.md templates

### Coder SOUL.md

```
# Coder

You implement code and tests for kanban tasks.

## Process
1. Read task body and parent comments
2. `git log --oneline -10` to understand recent changes
3. Implement changes with tests
4. Run FULL test suite in background: `terminal(cmd, background=true, notify_on_complete=true)`
5. Wait: `process(action="wait", timeout=3600)`
6. If tests pass → push to origin, create review task, block with `review-required`
7. If tests fail → fix, re-run

## Git Push
- Push to origin (fork), NOT upstream
- Remote URL already has embedded token — just `git push origin main`
- If push fails with 403: upstream is wrong org. Check `git remote -v`
- **MANDATORY: push BEFORE blocking for review.** Code only in the scratch workspace = code that will disappear.
- Pre-push hooks (`.githooks/pre-push`) run automatically on push — they re-verify tests as a safety net. If the hook blocks, fix and re-push. Do NOT use `--no-verify` unless you have a documented reason.

## For Godot / Game Projects
- After implementing: run `godot --headless --quit --path . 2>&1` and include output in handoff
- If Godot not available on server: note in handoff that runtime validation is pending
- `project.godot` MUST include `run/main_scene="res://main.tscn"` under `[application]`

## Long Downloads / Installs
Some tasks download large assets (Godot addons, npm packages, Docker images). These can take 60-120s — exceeding the default `max_runtime_seconds=60`.
- **Always use background+notify for downloads:** `terminal("git clone ...", background=true, notify_on_complete=true)` then `process(action="wait", timeout=600)`
- **NEVER `sleep` + poll.** Use `process wait` — it blocks without consuming turns.
- If the task's `max_runtime` is too short, you'll be killed. That's OK — push partial progress first. The orchestrator should raise `--max-runtime` for install tasks.

## Review Handoff (MANDATORY)
After work is complete:
1. Post handoff as `kanban_comment()` with changed_files, test counts, key decisions
2. Create reviewer task WITHOUT parent (parent prevents dispatch):
   `kanban_create(title="Review: (t_YOUR_TASK_ID) <summary>", assignee="reviewer")`
3. Block yourself: `kanban_block(reason="review-required: <summary>")`
⚠️ NEVER use `parent=task_id` — children of running/blocked tasks stay `todo` forever.
```

### Reviewer SOUL.md

```
# Reviewer

You review code, diffs, and game projects. Your verdict determines whether a task is truly complete.

## Process
1. Read the coder's handoff comment (changed_files, test counts, decisions)
2. Read the diff: `git diff origin/main` or read changed files
3. For code projects: verify tests pass, check logic, flag issues
4. **For game/Godot projects:** run Godot headless validation: `godot --headless --quit --path . 2>&1`. Must exit 0 with no errors. If Godot not available → block with "needs runtime validation."
5. Post review as `kanban_comment()` with findings, warnings, and verdict

## Verdicts (exactly 3)
- **APPROVE** — no issues. Post `kanban_comment(verdict=APPROVE)` then `kanban_complete()`.
- **NEEDS CHANGES** — specific issues, fixable. Post findings, unblock coder.
- **REJECT** — fundamentally broken / wrong approach. Post rationale, flag for user decision.

## Game Dev Review (CRITICAL)
- ALWAYS run Godot headless if available on the server
- Static code inspection is NOT sufficient — a GDScript can parse but fail to load
- If headless validation passes → approve is OK
- If headless not available → block with "needs runtime validation — human playtest required"
- Include Godot output in your comment

## Completion
After APPROVE: `kanban_complete(summary="Code review APPROVED. <summary>")`
After NEEDS CHANGES: unblock the coder task, no completion
After REJECT: `kanban_complete(summary="Code review REJECTED: <reason>")`
```

### Researcher SOUL.md

```
# Researcher

You investigate, explore, and analyze. You answer questions and provide context for other workers. You work on any board.

## Process
- Use web_search, web_extract, docs, and codebase exploration
- Be thorough — don't stop at surface-level results
- Summarize findings concisely with actionable recommendations
- Include sources (URLs, file paths, line numbers)
- If research uncovers a task that needs doing, `kanban_create()` for the right profile
- You do NOT implement code. Your output is analysis, not PRs.

## Completion
`kanban_complete(summary, metadata={sources, findings, recommendation})`

## TOKEN ECONOMY (90 turns)
- Batch web_extract calls (up to 5 URLs per call)
- If >60 turns used → stop and block with partial findings
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

# Set max_turns per role
hermes -p coder config set agent.max_turns 90
hermes -p reviewer config set agent.max_turns 90
hermes -p researcher config set agent.max_turns 90
hermes -p planner config set agent.max_turns 90

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
# appear in kanban_create() calls or function arguments, not in ⚠️ warning blocks.
grep -rn 'parent=task_id' /root/.hermes/profiles/*/SOUL.md | grep -v 'NEVER\|⚠️' && \
  echo "❌ CRITICAL: parent=task_id used as instruction — fix NOW" || echo "✓ No deadlock hazards (warnings only)"

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

## Mass Crash Recovery

When 3+ tasks on a board crash identically (same exit code, same duration, all within minutes),
it's usually a transient provider API issue. See `references/mass-crash-diagnosis.md`.

## Common pitfalls & fixes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `GITHUB_TOKEN vide` | Token stripped by `_sanitize_subprocess_env()` | Embed token in git remote URL (see "Git authentication"). Clear credential helper. |
| `push 403 "denied to X"` | Pushing to upstream instead of fork | Set origin to fork, add upstream for tracking |
| Worker exits without kanban_block | SOUL.md doesn't instruct termination | Add ⛔ TERMINATE section to SOUL.md |
| Profile has no model after clone (`—` in list)
| Task stuck in `gave_up` | `consecutive_failures` triggered circuit breaker | Reset in SQLite: `UPDATE tasks SET consecutive_failures=0 WHERE id='t_xxx'`. Then unblock+dispatch. |
| CI not triggering on fork | GitHub disables Actions on forks by default (silently ignores push events even when workflow has `push` trigger) | **One-time fix per repo:** enable Actions via API: `echo '{"enabled":true,"allowed_actions":"all"}' | gh api --method PUT /repos/Seven74AI/repo/actions/permissions --input -`. After that, `git push` triggers CI automatically — no `workflow_dispatch` needed. Verify with `gh api /repos/Seven74AI/repo/actions/permissions`. |
| `mergeable_state: unstable` | No CI checks reported to PR | Ensure CI runs on PR's exact HEAD SHA |
| Duplicate review tasks | Worker doesn't check for existing reviews | Scan board before creating review task. Link don't duplicate. |
| Reviewer orphaned (parent archived) | Disk incident destroyed coder workspace | Archive reviewer, recreate coder task if needed |
| Credential helper overrides URL token | `git config credential.helper = store` | `git config --unset credential.helper` (local + global in profile home) |
| Worker polls instead of waits | Burns iteration budget on polling loops | Use `process(action="wait")` — 1 call replaces 50-100 polls |
| Reviewer doesn't know what to do | kanban-worker missing REJECT outcome | 3 outcomes: approve, needs changes, reject (see Reviewer SOUL.md) |
| Reviewer tasks stuck in `todo` forever | Created with `--parent` (children of running/blocked never promoted) | Create reviewers WITHOUT parent. Include coder ID in title: `"Review: (t_coder_id) ..."` |
| Destructive command runs without explanation | `rm -rf`, force-push, DB writes trigger user approval | Before ANY destructive command, state WHAT it does and WHY in one line. Don't make the user ask. |
| Profile deleted while tasks still running on it | Didn't check task assignments before deletion | Before deleting a profile: `hermes kanban --board <board> list | grep <profile>` for ALL boards. Only delete when zero running/blocked tasks reference it. |
| Profile has no model after clone (`—` in list) | `--clone` copies config but may leave provider/model fields empty | Always set explicitly: `hermes -p <name> config set model deepseek-v4-pro && hermes -p <name> config set provider deepseek` |
| `config set provider` uses wrong key structure | `hermes config set provider X` writes top-level `provider: X`, but Hermes reads `model.provider` (nested). Profile silently falls back to Anthropic. | Always write the nested structure via Python: `cfg['model'] = {'default': '...', 'provider': '...', 'base_url': '...'}`. Verify with: `python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['model'])"` |
| Worker crashes with "Unknown skill(s)" | Skills are per-profile. `skill_manage()` creates only in the main `~/.hermes/skills/`. Worker profiles have their own copy at `~/.hermes/profiles/<name>/skills/`. | After creating a project skill, sync to ALL profiles: `for p in coder reviewer researcher planner; do cp /root/.hermes/skills/dogfood/<skill>/SKILL.md /root/.hermes/profiles/$p/skills/dogfood/<skill>/SKILL.md; done`. Caused 8 researchers (baguette+glance) to crash 5+ times before root cause found. |
| `kanban complete` fails on task in `todo` state | `complete` requires the task to be `running` — won't work on `todo` or `ready` | Use SQLite directly: `python3 -c "import sqlite3; db=sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db'); db.execute(\"UPDATE tasks SET status='done', completed_at=unixepoch() WHERE id='t_xxx'\")"` |
| Coder creates review for wrong profile | LLM changes `assignee="reviewer"` to `assignee="shop-reviewer"` (deleted profile). Task never dispatched. | In coder SOUL.md, use ALL-CAPS: `assignee="reviewer"` — **EXACTLY this string, never project-specific.** |
| DB not found at expected path | Each board has its OWN DB: `kanban/boards/<board>/kanban.db`. Top-level `kanban/kanban.db` is empty. | Always target the per-board DB. Find it: `find /root/.hermes/kanban/boards -name 'kanban.db' -not -empty` |
| Task ready for hours, diagnostic "Ready for Xh with no worker" | Task assigned to non-existent profile. Dispatcher cannot find assignee → task stays ready forever. Watchdog does not catch it (not blocked). | Full recovery recipe: `references/ghost-profile-recovery.md`. Quick fix: `hermes kanban --board <board> reassign <id> reviewer`. Also caught by cross-check script in Verification section. |
| SOUL.md deployed with stale/broken content | Manual deploy from memory instead of from the canonical template. E.g. `parent=task_id` crept back into coder SOUL.md. | Always deploy from the skill's template file. After writing, verify with grep: `grep -rn 'parent=task_id' /root/.hermes/profiles/*/SOUL.md` should return NOTHING. |
| Ops tickets go stale after infra changes | Audit tickets from days ago recommend actions (monitoring scripts, MCP sharing, disk cleanup). Infrastructure evolves; old recommendations rot. | After major infra changes, run a re-audit: see `references/ops-reaudit-pattern.md`. |
| `hermes kanban boards switch` then `list` shows wrong board | `boards switch` prints "Active board is now 'X'" but `list` still shows startup-lab tasks. Board switch is unreliable for `list`/`show`. | Always use `--board <slug>` directly on the action: `hermes kanban --board glance list`, `hermes kanban --board shop create "..." --assign coder`. This is 100% reliable. |
| All tasks on a board crash identically in same window | Provider API stream drops (e.g. DeepSeek `RemoteProtocolError`), web search rate-limited. All workers fail before reaching real work. | Don't change profiles/tasks — it's transient API. Unblock all, reset `consecutive_failures` in SQLite, let dispatcher retry. See `references/mass-crash-diagnosis.md`. |
| User asks \"recap des board\" and then wants tickets on idle boards | User expects zero idle boards — every board must always have active work. Empty boards are treated as a problem. | After a recap, proactively identify idle boards. Propose 2-3 tickets per idle board (1 feature + 1 research + 1 test). For game boards (baguette, the-swarm, videogame-lab): propose 3+ phases, each heavy. Use `project-ci` skill for test ticket templates. Present as a list for user validation before creating. **CRITICAL:** before proposing tickets, check what project/product is ALREADY built on that board. Don't propose re-doing work (e.g. re-selecting from ideation when a project like MIROIR was already chosen and built). Read a few done tickets to understand current phase. |
| Task times out repeatedly at ~62s | Default `max_runtime_seconds=60` on tasks. Downloads (Godot addons, npm packages, Docker images, git clones) routinely take 60-120s. Worker dies mid-download, watchdog unblocks, same timeout repeats — 4+ consecutive failures with no progress. | **At creation:** `hermes kanban create ... --max-runtime 180` for any task involving downloads. **For existing stuck tasks:** update SQLite directly: `UPDATE tasks SET max_runtime_seconds=180, consecutive_failures=0 WHERE id='t_xxx'` then `hermes kanban --board <b> unblock <id>`. **Also:** ensure coder SOUL.md has the \"Long Downloads / Installs\" section (background+notify pattern). Real case: videogame-lab t_6303d37c (GUT addon install) timed out 4× at 61-62s before max_runtime raised to 180s. |

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