# Diagnosing Blocked Kanban Tasks

Quick-reference guide for the Block Watchdog and any agent investigating why a task is blocked. Read the block reason, match the pattern, apply the fix.

## Common Block Patterns

### 1. `review-required: ...`

**What it means**: The coder finished their work and created a reviewer task before blocking themselves. This is NORMAL — the review-gate pattern.

**What to check**: Does the review task exist and is it assigned to a reviewer profile?

```bash
# Find review task ID in the block reason
hermes kanban --board <board> show <task_id> | grep "Review task:"
# Check review task status
hermes kanban --board <board> show <review_task_id> | grep "status:"
```

**Action**:
- Review task exists and is `ready`/`todo` → NO ACTION. The dispatcher will pick it up when a slot is free.
- Review task is `done` or doesn't exist → unblock the parent, the review was handled.
- Review task is `blocked` → diagnose THAT task instead.
- If review tasks pile up because all slots are taken by coders (max_spawn bottleneck) → wait for a slot to free. This is expected with low max_spawn.

### 2. `Iteration budget exhausted (90/90)`

**What it means**: The worker used all 90 API iterations without completing. This is a TECHNICAL FAILURE — the task is too complex for the agent loop.

**Patterns**:
- **Long test suites run inline**: Worker runs `npx playwright test` inside the agent loop, burning iterations on test output. FIX: update task body to use `terminal(background=true, notify_on_complete=true)`.
- **Benchmark loops**: Worker iterates on config → run benchmark → read results → tweak → repeat. Each benchmark run burns 20-30 iterations. FIX: create a wrapper script that does the full cycle in one background call.
- **Polling after background launch**: Worker correctly launches script in background, then burns iterations polling (`sleep 10 && tail logfile`) instead of using `process(action="wait")`. One `process wait` call replaces 50-100 polling iterations. FIX: update task body to instruct `process(action="wait", timeout=3600)`.
- **Genuinely complex task**: 90 iterations legitimately not enough. FIX: split into smaller sub-tasks, OR increase the profile's `agent.max_turns` in config.yaml (e.g., 90 → 360).
- **Config change not yet applied**: Profile's `max_turns` was increased but the current run started BEFORE the change. Config changes only apply to NEW spawns. FIX: unblock the task so it re-dispatches with the updated config.

**Action**:
1. Check how many runs have hit this: count `blocked.*budget exhausted` events
2. If >2 runs → the task body needs updating with background instructions, OR the task needs splitting
3. If profile's `max_turns` was recently increased → verify the current run started AFTER the config change. If not, unblock for re-dispatch.
4. Unblock with a comment explaining the fix applied

### 3. `GITHUB_TOKEN` / `push blocked` — the token is empty

**What it means**: Worker tried to `git push` and found `GITHUB_TOKEN` empty — `echo $GITHUB_TOKEN` returns nothing, or `git` credential helper complains the variable is unset. The worker blocks with a message asking you to `export GITHUB_TOKEN=xxx`.

**⚠️ TWO DISTINCT ROOT CAUSES. Diagnose before acting.**

#### Cause A: Token stripped by `_sanitize_subprocess_env()` — use token-in-URL

**What happens**: The gateway HAS `GITHUB_TOKEN` in `os.environ`. The dispatcher copies it into the worker env. But `_sanitize_subprocess_env()` removes it from every shell subprocess because it's a Copilot provider credential.

**Fix (chosen — token-in-URL, not env_passthrough):** Embed the token in the git remote URL. This survives the env sanitizer without leaking the token into ALL shell subprocesses (npm install, ls, echo — everything would see it). Combined with the fork workflow:

```bash
TOKEN=$(grep '^GITHUB_TOKEN=' ~/.hermes/.env | head -1 | cut -d= -f2-)
cd <workspace>
git remote set-url origin "https://git:${TOKEN}@github.com/Seven74AI/<repo>.git"
git remote add upstream "https://github.com/mnlamart/<repo>.git"
# CRITICAL: credential helper overrides URL-embedded tokens
git config --unset credential.helper 2>/dev/null
HOME=/root/.hermes/profiles/<profile>/home git config --global --unset credential.helper 2>/dev/null
git fetch upstream main
```

**Why not `terminal.env_passthrough`**: It would pass the token into EVERY shell subprocess (every `npm install`, every `echo`). A malicious postinstall script could exfiltrate it. Token-in-URL is scoped to `git push` only — the security sanitizer stays intact for all other commands.

#### Cause B: Git remote misconfigured or wrong repo

**What happens**: The token is present in the environment but `git remote -v` points to the wrong org/repo, or the remote URL uses literal `***` placeholder instead of a real token.

**CRITICAL — before unblocking**: Check if the git remote already has a working token:
```bash
cd /path/to/repo && git remote -v | head -2
# If it shows oauth2:***@github.com with a REAL token (not literal ***), push works.
# Verify with: git push origin main --dry-run
```

**If a credential helper is configured** (`git config credential.helper`), it can **override URL-embedded tokens** with empty stored credentials. Clear it before relying on URL-embedded tokens:
```bash
git config --unset credential.helper 2>/dev/null
# Also clear the global one in the profile home:
HOME=/root/.hermes/profiles/<profile>/home git config --global --unset credential.helper 2>/dev/null
```

**Fork-vs-upstream pattern**: If the token belongs to user X and the repo is under org Y, check if user X has a fork:
```bash
curl -s -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/$USER/$REPO" | grep '"fork"'
# true = it's a fork → push to origin (fork), create PR to upstream
# false / 404 = direct repo or no access
```
If it's a fork, ensure `origin` points to the fork (not upstream), add `upstream` for the source repo, and push to `origin`. Do NOT try to push to upstream directly — the token won't have write access.
```bash
git remote set-url origin https://<user>:<token>@github.com/<user>/<repo>.git
git remote add upstream https://github.com/<upstream-org>/<repo>.git
```

**Also verify the repo actually exists under that org:**
```bash
gh api repos/<org>/<repo> 2>&1 | head -3
# 404 = wrong org or repo name. 401 = token lacks access. 200 = OK.
```

**Context**: Project `.env` files often have `GITHUB_TOKEN="MOCK_GITHUB_TOKEN"` for the APPLICATION's GitHub OAuth feature. This is NOT the token for git push. The real token lives in `~/.hermes/.env` and should be configured in the git remote URL.

**Action**:
- Remote already has a real token → unblock, add comment explaining the remote is configured
- Remote has literal `***` or broken auth → configure the remote with the real token from `~/.hermes/.env`, then unblock
- DO NOT tell the worker to put the token in the project `.env` — that's for the app, not git

**🍴 Fork PR workflow (when you don't have write access to upstream):**

When the token belongs to user X but the task targets a repo under org Y (and X doesn't have push access to Y's repo), the correct flow is:

```
1. Push to fork (origin)     → CI runs on the fork
2. CI passes                 → validation gate
3. Create PR to upstream     → from fork to org Y's repo
```

**Setting up the fork remote** (run once per workspace, then unblock the task):
```bash
TOKEN=$(grep '^GITHUB_TOKEN=' /root/.hermes/.env | head -1 | cut -d= -f2-)
cd <workspace>
# Point origin to the fork with embedded token
git remote set-url origin https://git:${TOKEN}@github.com/<user>/<repo>.git
# Add upstream as the source-of-truth (no auth needed for fetch)
git remote add upstream https://github.com/<upstream-org>/<repo>.git
git fetch upstream main
```

**⚠️ CI on forks: push alone may not trigger workflows.** GitHub Actions on forks sometimes don't auto-trigger on push events, even when Actions are enabled (`enabled: true` in the repo's actions/permissions API). Symptoms: `pushed_at` updates but `actions/runs` shows 0 runs.

Fix: add `workflow_dispatch:` to the workflow file's `on:` trigger, then dispatch manually:
```bash
# 1. Edit .github/workflows/deploy.yml on the fork — add `workflow_dispatch:` to the `on:` block
# 2. Trigger via API
WORKFLOW_ID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/<user>/<repo>/actions/workflows" | \
  python3 -c "import json,sys; [print(w['id']) for w in json.load(sys.stdin)['workflows'] if w['name']=='🚀 Deploy']"
)
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/<user>/<repo>/actions/workflows/${WORKFLOW_ID}/dispatches" \
  -d '{"ref":"main"}'
# 3. Monitor: curl -s -H "Authorization: Bearer $TOKEN" \
#    "https://api.github.com/repos/<user>/<repo>/actions/runs?per_page=1"
```

**Kanban structure for fork PRs** (two linked tasks):
```bash
# Task A: CI validation (ready — worker checks CI status, blocks until green)
hermes kanban --board <board> create "CI: validate CI passes on fork" \
  --assignee <coder-profile> --tenant <tenant>

# Task B: PR creation (blocked on Task A — worker creates PR fork→upstream)
hermes kanban --board <board> create "PR: create PR fork→upstream" \
  --assignee <coder-profile> --tenant <tenant>
hermes kanban --board <board> block <task_b_id> "waiting: CI must pass on fork (<task_a_id>)"
hermes kanban --board <board> link <task_a_id> <task_b_id>
```

### 4. Duplicate tasks

**Symptom**: Multiple identical tasks blocked with the same reason (e.g., 4 review tasks for the same parent).

**Prevention**: Before creating a review task via `kanban_create`, scan the board for an existing review of the same work. Check if a task with a similar title already exists in `ready`, `running`, `todo`, or `blocked` status. If found, link to it instead of creating a duplicate.

**Action**: Archive the duplicates — the kanban has no `cancel` command:
```bash
hermes kanban --board <board> archive <duplicate_id>
```
Keep only one instance. Archived tasks still show in counts but are excluded from `list` by default.

### 5. `crashed` / `pid not alive`

**What it means**: The worker process died unexpectedly. Could be OOM, signal, or gateway restart.

**Action**:
- Check if system is under memory pressure: `free -h`, `dmesg | grep -i oom | tail -5`
- Check if gateway restarted recently: `systemctl status hermes-gateway`
- No OOM, no restart → unblock, task will retry
- OOM detected → check `references/kanban-autoscale.md` for diagnosis

### 5b. Protocol violation: `worker exited cleanly (rc=0) without calling kanban_complete or kanban_block`

**What it means**: The worker ran successfully, completed its work, posted comments — then the Python process ended without calling a terminal kanban function. The session log is clean but the task is marked `crashed`.

**Root cause**: The worker's SOUL.md says "post findings" but never instructs the worker to call `kanban_block()` or `kanban_complete()` after finishing. The worker does the work, then exits — protocol violation.

**Diagnosis**: Check if this is a continuous/watcher task:
```bash
hermes kanban --board <board> show <task_id> | grep "continuous\|runs continuously\|watcher\|watch"
```

**Fix for continuous tasks**: Add a ⛔ TERMINATE section to the watcher's SOUL.md with absolute language (`YOU MUST`, `ABSOLUTE REQUIREMENT`) and a time limit (>5 min or >30 tool calls = STOP and block). Full template in `references/continuous-task-termination.md`.

**Fix for one-shot tasks**: The worker should call `kanban_complete()` when done. Ensure the SOUL.md says so explicitly.

**Circuit breaker**: After 3-5 protocol violations, the dispatcher `gave_up` and the task stops being dispatched. Reset in SQLite:
```bash
python3 -c "
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
db.execute(\"UPDATE tasks SET consecutive_failures = 0 WHERE id = '<task_id>'\")
db.commit()
db.close()
"
# Then unblock + dispatch
```

### 7. Coders blocked `review-required` + reviewers stuck in `todo` — parent-child deadlock

**Symptom**: Coder tasks are blocked with `review-required`, reviewer tasks exist but are stuck in `todo` status forever. Multiple dispatch passes show "Promoted: 0, Spawned: 0" for these tasks.

**Root cause**: The kanban dispatcher does not promote `todo` children of blocked or running parent tasks. When a reviewer is created with `parent=coder_task_id`, and the coder is blocked `review-required`, the reviewer can never leave `todo`.

**Diagnosis**:
```bash
# Check if reviewers have parents
hermes kanban --board <board> show <reviewer_id> | grep parents
# Check parent status
hermes kanban --board <board> show <parent_id> | grep status
```

**Fix**: Archive the stuck reviewers and recreate them without `parent=`:
```bash
# Archive deadlocked reviewers
hermes kanban --board <board> archive <reviewer_id>

# Recreate WITHOUT parent link
hermes kanban --board <board> create "Review: <title> (from <coder_id>)" \
  --assignee reviewer --tenant <tenant>
# Then dispatch
hermes kanban --board <board> dispatch
```

**Prevention**: NEVER use `parent=` when creating reviewer tasks. Include the coder task ID in the body text as a reference instead. The block watchdog will unblock the coder when the reviewer completes.

**What it means**: Someone (or the system) reclaimed the task from the worker. The worker was terminated.

**Action**: Usually no action needed — the task is already back in `ready` and will be re-dispatched. Check the comment thread for context on why it was reclaimed.

## General Diagnosis Flow

```
1. Read block reason → match pattern above
2. If review-gate → check review task status
3. If technical failure → check run count, update body or split
4. If token/auth → verify remote configuration, don't touch project .env
5. If duplicate → archive extras
6. Unblock with explanatory comment
```

## When NOT to unblock

- **Review-gate with review task still pending** → let the review process work
- **Token needed that we genuinely don't have** → block with clear request to user
- **Task that has failed 10+ times with same error** → something is fundamentally wrong, ask user
