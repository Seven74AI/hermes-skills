---
name: kanban-project-workflow
description: "Shared kanban worker workflow patterns for all project boards — label-based PRs, respawn guard, selective profile skill management, worker tuning, PR consolidation, native vs custom infrastructure audit."
version: 1.13.0
metadata:
  hermes:
    tags: [kanban, workflow, pr, ci, shared, anti-specs-to-code]
---

# ⛔ RÈGLE ABSOLUE — LIRE AVANT TOUTE ACTION

**This is the ONE authoritative source for CI merge rules. Do NOT duplicate this
block into project-level skills (shop, the-swarm, etc.). Project skills should
reference `kanban-project-workflow` and tell coders to load it. Duplication
creates maintenance drift — when the rule evolves, outdated copies in project
skills silently contradict the authoritative version.**

**TU NE MERGES PAS SI UN SEUL CHECK CI EST ROUGE. ZÉRO EXCEPTION.**

1. `gh pr merge --admin` = **INTERDIT**. Tu ne l'utilises jamais.
2. Seul `gh pr merge --auto --squash` est autorisé.
3. Check rouge → tu **FIXES**. Même si l'erreur est "pré-existante" ou "pas ton code".
4. Tu n'évalues pas, tu ne rationalises pas. Rouge = tu fixes.
5. **TOUS les checks doivent être GREEN** avant de créer le reviewer.
6. Si vraiment unfixable → tu bloques et tu expliques. Tu ne merges pas.

---

# Kanban Project Workflow — Shared Patterns

Universal kanban worker patterns for all project boards (shop, the-swarm, music-library, etc.).
Load this skill alongside the project-specific skill for every coder/reviewer task.

## Unified Workflow

ALL projects use the same flow — review-gated with auto-merge:

```
Coder → Implement + Run CI → CI ALL GREEN → PR + auto-merge → block "review-required" → Reviewer approves → GitHub merges auto → CI watchdog unblocks → Coder completes
```

⚠️ **CRITICAL: The coder MUST verify CI is 100% GREEN BEFORE creating the reviewer task and blocking.** If CI is red, the coder MUST fix it first. Never block with red CI — the auto-merge will never complete, and the coder will be stuck in a respawn loop.

This replaces the previous two-model system (CI-gated for shop, review-gated for the-swarm).
GitHub's native auto-merge (`gh pr merge --auto`) handles the merge — no custom merge logic needed.

### Reviewer Identity (GitHub App)

The reviewer agent must approve PRs as a DIFFERENT GitHub identity from the coder.
GitHub does NOT count the PR author's own approve. The reviewer uses a **GitHub App**
installed on the target repos, authenticating as `hermes-reviewer[bot]`.

Setup reference: `references/github-app-reviewer-setup.md`
Branch protection: require 1 approval, require CI checks, allow auto-merge.

## GitHub Models

Two repo models — your project skill tells you which one.

### Fork Model (shop, music-library)

Push to `Seven74AI/<repo>` fork. Workers NEVER push directly to upstream (`mnlamart/<repo>`).
Only consolidation PRs go to upstream. Coder PRs + reviews happen entirely on the fork.

```
Worker branch → Seven74AI/<repo> fork → PR + auto-merge + review on fork
Consolidation: fork main → PR to mnlamart/<repo> upstream (manual)
```

### Direct Model (the-swarm, videogame-lab)

Push directly to `Seven74AI/<repo>`. No upstream fork.

```
Worker branch → Seven74AI/<repo> (direct push, one repo)
```

## Unified PR Workflow (ALL project boards)

**Single workflow for every board — shop, the-swarm, music-library, etc.**
One flow: CI gates correctness, reviewer agent gates quality, GitHub native
auto-merge handles the rest. No per-project variation.

```
Coder → PR + auto-merge → block (review-required) → Reviewer agent approves
       → CI green → GitHub auto-merge → Light watchdog unblocks → Coder complete
```

### Coder (step-by-step)

⚠️ **DO NOT BLOCK FOR REVIEW UNTIL CI IS 100% GREEN.** If you block with red CI,
the auto-merge will never complete and you'll be stuck in a respawn loop.

```python
# 1. Clone repo, implement, run CI LOCALLY
terminal("pnpm typecheck && pnpm vitest run && pnpm lint && pnpm playwright test", 
         background=true, notify_on_complete=true)
# WAIT for CI — DO NOT proceed until ALL checks pass

# 2. Push branch, create PR with kanban label AND auto-merge
terminal(f"gh pr create --repo {REPO} --base main --head feat/X "
         f"--label 'kanban:{os.environ[\"HERMES_KANBAN_TASK\"]}' "
         f"--title '...' --body '...'")
terminal(f"gh pr merge --auto --squash")

# 3. ⚠️ WAIT for remote CI — verify EVERY check is GREEN
#    gh pr checks <N> --repo <REPO>
#    If ANY check is FAILURE → FIX IT. Go back to step 1.
#    Do NOT merge. Do NOT use --admin. Fix the failures.

# 4. ONLY when ALL checks are GREEN:
#    - Create reviewer task (standalone — NEVER with parent=)
#    - Post handoff comment with changed files summary
#    - Block yourself
kanban_create(
    title=f"Review: (t_{os.environ['HERMES_KANBAN_TASK']}) <summary>",
    assignee="reviewer",
    skills=["github-code-review", "kanban-project-workflow"],
    body="Review the work from the coder task.",
)
kanban_comment(body="review-required handoff: ...")
kanban_block(reason="review-required: ALL CI GREEN — PR label kanban:$HERMES_KANBAN_TASK")
```

⚠️ **If CI is red at step 3:** Do not create reviewer. Do not block. Fix the failures.
The respawn guard will block you if you try to respawn with a PR URL in comments.
**Fix CI first, then block.**

GitHub auto-merge (`--auto`) handles the CI gate natively — no custom watchdog
needed for merging. When all required status checks pass AND the reviewer
approves, GitHub merges automatically.

### ⛔ Pitfall: Coder blocks for review but forgets to create reviewer task

**This is the #2 cause of PR pile-up** (after missing `kanban-project-workflow` skill).
The coder follows steps 1-3 correctly (PR + auto-merge + CI green + block) but skips
step 4 (creating the reviewer task). Result: PR sits open forever with CI green and
auto-merge enabled, but nobody ever reviews it. The coder is blocked in kanban, the
reviewer has no task to pick up — deadlock.

**Symptoms:**
- Multiple open PRs with CI green, auto-merge enabled, zero reviews
- Coders all `blocked` with `review-required`, but zero `reviewer` tasks in `running` or `ready`
- Board accumulates PRs over hours/days with no merges

**Detection:**
```bash
# Count open PRs with auto-merge enabled but no reviews
gh pr list --repo <repo> --state open --json number,reviews,autoMergeRequest \
  --jq '[.[] | select(.autoMergeRequest != null and (.reviews | length) == 0)] | length'
# Compare to reviewer tasks on the board
hermes kanban --board <board> list --status running | grep reviewer | wc -l
# If PRs >> reviewer tasks → coders forgot step 4
```

**Recovery — bulk-create reviewer tasks for all green PRs:**
```python
# For each open PR with CI green:
# 1. Enable auto-merge (if not already): gh pr merge <N> --auto --squash
# 2. Create reviewer task:
#    hermes kanban --board <board> create --assignee reviewer \
#      --skills github-code-review --skills kanban-project-workflow \
#      "Review: (<task_id>) <pr_title>"
# 3. Dispatch: hermes kanban --board <board> dispatch
```

**Prevention:** The coder step-by-step (§ 4) already mandates creating the reviewer task.
The absolute rule at the top of this skill exists to ensure step 4 is never skipped.

**Real case:** the-swarm board (2026-05-29) — 16 PRs open, all CI green, all auto-merge
enabled, all coders blocked `review-required`, zero reviewer tasks. PRs had been piling
up for hours. Fixed by bulk-creating 16 reviewer tasks → all approved and merged within
minutes.

### ⛔ Pitfall: `active_pr` Respawn Guard Blocks Coder After Review

When the coder blocks with a handoff comment containing the PR URL, the respawn
guard (`active_pr` check in `kanban_db.py`) prevents the coder from respawning
after the reviewer unblocks. **30+ consecutive `respawn_guarded: active_pr`
events** hold the task in `ready` for 5-10 minutes.

**Why:** The guard checks for PR URLs in task comments within the last 24h.
The coder's own handoff comment triggers it.

**Fix — never put the PR URL in your own comment.** Post the handoff without
the URL, or use the kanban task metadata. The reviewer can find the PR from
the coder's work context. If already stuck, delete the comment:
```sql
DELETE FROM task_comments WHERE task_id='<id>' AND body LIKE '%github.com%pull%';
```

Real case: t_541d2c3a (2026-05-28) — 30 respawn_guarded events over 10 minutes
because the coder's `review-required handoff` comment contained the PR URL.
Deleting the comment cleared the guard immediately.

### Reviewer agent (step-by-step)

The reviewer MUST authenticate as a DIFFERENT GitHub identity from the coder
(Seven74AI). GitHub does NOT count the PR author's own approve. The reviewer
uses a **GitHub App** (`hermes-sevenai-reviewer`, App ID 3788528) installed on
the target repos. See `references/github-app-reviewer-setup.md`.

**Token generation:** The reviewer generates a fresh installation token at the
start of EACH run. A helper script is bundled at `scripts/gen-installation-token.py`
and must also be present at `~/.config/gen-installation-token.py` in the reviewer
profile's HOME.

```python
# 1. Read coder's handoff from their task comment thread
kanban_show()

# 2. Generate GitHub App installation token
terminal("TOKEN=$(python3 ~/.config/gen-installation-token.py) && echo OK")

# 3. Review the PR (pull diff, read code, run tests)
terminal(f"TOKEN=$(python3 ~/.config/gen-installation-token.py) && "
         f"GH_TOKEN=$TOKEN gh pr diff {PR_NUMBER} --repo {REPO}")

# 4a. Approve — unblocks auto-merge
terminal(f"TOKEN=$(python3 ~/.config/gen-installation-token.py) && "
         f"gh api repos/{REPO}/pulls/{PR_NUMBER}/reviews "
         f"-H 'Authorization: Bearer $TOKEN' "
         f"-f event=APPROVE -f body='LGTM — reviewed by agent'")
kanban_complete(
    summary="Reviewed PR #N; approved — code correct, tests pass",
    metadata={"approved": True}
)

# 4b. Request changes — auto-merge blocked
terminal(f"TOKEN=$(python3 ~/.config/gen-installation-token.py) && "
         f"gh api repos/{REPO}/pulls/{PR_NUMBER}/reviews "
         f"-H 'Authorization: Bearer $TOKEN' "
         f"-f event=REQUEST_CHANGES -f body='<specific feedback>'")
kanban_comment(body="Changes requested: <specific feedback>")
kanban_block(reason="changes-requested: <summary> — coder must fix")
```

### Light CI watchdog (simplified — only unblocks)

The CI watchdog no longer merges PRs (GitHub auto-merge does that). It only
detects merged PRs and unblocks the corresponding kanban task. See
`references/ci-watchdog-light.md` for the ~30-line script.

```python
# Poll for merged PRs with kanban labels, then:
for task_id in merged_pr_tasks:
    terminal(f"hermes kanban --board {board} unblock {task_id}")
```

### Coder respawn (after unblock)

```python
kanban_show()
# Verify merge completed, run final CI
kanban_complete(summary="PR #N merged via auto-merge — CI green, reviewer approved")
```

### Why this replaces the old split (CI-gated vs review-gated)

- **Old shop (CI-gated):** no reviewer, CI watchdog did merge + unblock.
  But the user wants code review on ALL boards, not just the-swarm.
- **Old the-swarm (review-gated):** reviewer approved manually, no auto-merge.
  But the user wants full automation (CI + review → auto-merge).
- **Unified:** CI gates correctness, reviewer gates quality, GitHub auto-merge
  does the rest. One workflow, zero per-board variation.

## Infrastructure: Native Hermes vs Custom (AUDIT)

Before building more custom watchdogs, understand what Hermes kanban does
natively vs what we built ourselves. See `references/native-vs-custom.md`.

**Quick reference:**
- ✓ Native: dispatcher, worker lifecycle, stale reclaim, failure auto-block,
  child promotion, auto-decompose, workspace GC, idempotent create
- ✗ Custom: CI watchdog (we built), block watchdog (we built), pre-spawn
  watchdog (we built), workspace GC cron (redundant with native `hermes kanban gc`)

The block watchdog and CI watchdog are custom infrastructure. When debugging
kanban issues, check them before assuming Hermes core is broken.

## Pitfall: `|| true` in CI Steps Silently Swallows Errors

GitHub Actions steps like `run: pnpm typecheck || true` always exit 0 even when
the command fails. TypeScript errors, lint violations, or test failures are
hidden — CI shows green while the codebase has real problems.

**Never use `|| true` on CI verification steps.** Each job step should fail
honestly. If a step legitimately can fail without being a problem, use
`continue-on-error: true` on the step instead — it marks the job as
yellow/warning, not green.

**Shop regression:** Commit `15f1d1e` (May 20) removed `|| true` from the
typecheck step. A later consolidation commit (`0774571`) re-introduced it.
Fixed on the Seven74AI fork via GitHub API commit `2dfdfce` (May 21).
Always check the workflow file after consolidation PRs — `|| true` is a
magnet for copy-paste regressions.

**Pitfall: local working copy corruption.** When the repo at `/tmp/shop-original`
accumulates `bad object` errors (corrupt git objects), `git push` fails with
`fatal: bad object <sha>`. Fix: delete and re-clone the working copy. The
GitHub API can be used for file edits in the meantime (as done for the
`|| true` fix).

## Pitfall: gh CLI Version Limitations

Older `gh` versions (pre-2.60) lack `--app-id` in `gh auth login` and `--search`
in `gh pr list`. Workarounds:

- **No `--app-id`:** Use `gh api` with explicit `-H "Authorization: Bearer $TOKEN"`
  instead of `gh pr review --approve`. The reviewer generates an installation token
  via JWT, then calls `gh api repos/.../pulls/N/reviews -H "Authorization: Bearer $TOKEN"`.
- **No `--search`:** Use `--json labels,number` + regex in Python to filter by label
  prefix (`re.match(r"kanban:", label["name"])`). `gh pr list --label kanban:` does
  exact match, not prefix — a label `kanban:t_abc123` does NOT match `--label kanban:`.

## Pitfall: `git merge main` pollutes feature branch history

**Never merge main into your feature branch.** Creates useless merge commits
("merge main", "sync remote") that clutter history and waste CI minutes.
Always rebase instead:

```bash
# ✅ CORRECT — rebase
git fetch origin main    # or: git fetch upstream main (fork model)
git rebase origin/main   # or: git rebase upstream/main
git push --force-with-lease

# ❌ WRONG — creates merge commits
git merge origin/main
```

Squash-merge on the PR cleans up the commits, but every push triggers CI —
merge commits = wasted CI minutes and noisy PR history.

## Pitfall: Task Stuck in Budget Exhaustion → Split and Use Background

When a coder task burns 90+ turns 2+ times consecutively, the root cause is
almost always **inline test/CI output consuming turns**. Every line of `vitest`
or `playwright` output counts as a turn. The fix is two-fold:

### 1. Use background mode for ALL test/CI runs

```python
# ✅ CORRECT — 1 turn for setup, 1 turn to wait
terminal("npx playwright test --grep combat", background=True, notify_on_complete=True)
process(action="wait", timeout=600)
# Read results from a file or parse the wait output

# ❌ WRONG — every test log line burns 1 turn
terminal("npx playwright test --grep combat", timeout=300)
```

### 2. Split large tasks into atomic sub-tasks

If a task has 3+ distinct fixes, split into separate tickets. Each sub-task
handles 1-2 fixes max, uses background mode, and can complete within the
budget. Archive the original bloated task.

```bash
# Create N atomic sub-tasks from the original
hermes kanban --board <board> create --assignee coder ... "[P1] Fix X — batch 1/N"
hermes kanban --board <board> create --assignee coder ... "[P1] Fix X — batch 2/N"
# Archive the original
hermes kanban --board <board> complete <original_task>
```

### 3. Bump max_turns to 120

Default 90 is too tight for any CI run. Set on all worker profiles:

```bash
hermes config set --profile coder max_turns 120
hermes config set --profile coder kanban.max_iterations 120
hermes config set --profile reviewer max_turns 120
hermes config set --profile researcher max_turns 120
```

Real case: t_8780761d (the-swarm, 2026-05-29) — 3 consecutive budget exhaustions
at 90/90 fixing 5 E2E combat failures. Split into 3 atomic sub-tasks each with
background CI. All profiles bumped to max_turns=120.

When a worker creates a branch from a fork, the fork may contain commits that
were **never merged to upstream main**. This happens when consolidation PRs,
dep bumps, or cleanup sweeps were pushed to the fork but the PR to upstream
was closed or never created.

**Symptoms:**
- PR diff shows unrelated commits (dep bumps, consolidation, cleanup) alongside
  the actual feature work.
- CI workflow regressions (`|| true`, wrong node version) reappear from old commits.
- Commits from days/weeks ago show in `git log` but not on upstream main.
- `gh api repos/X/compare/main...<branch>` shows diverged status.

**Prevention:** Before starting work, always rebase the fork on upstream main:
```bash
git fetch upstream main
git rebase upstream/main
git push --force-with-lease origin <branch>
```

**Real case — PR #109 on shop (2026-05-20):** Worker t_bbce3b35 branched from
a fork containing 5 stale commits (consolidation, deps, cleanup) from May 18-19.
These commits were never on upstream main. The PR showed 9 commits: 4 legit
(French translations) + 5 stale (including one that re-introduced `|| true`).
No CI triggered, no kanban label.

## ⛔ CRITICAL: NEVER Merge with Red CI — Auto-Merge Only

**The coder MUST NOT manually merge PRs.** Auto-merge (`gh pr merge --auto --squash`)
is the ONLY merge path for reviewed PRs. Manual merge (`gh pr merge --merge`) with
red CI bypasses all gates — the PR merges with failing checks, broken code lands on
main, and the kanban workflow doesn't detect it (CI watchdog only polls for auto-merged PRs).

**Symptoms:**
- `gh pr view` shows `mergedBy: Seven74AI`, `auto_merge: null` — manual merge, not auto
- `mergeStateStatus: BEHIND` or `UNKNOWN` but `state: MERGED`
- Required status checks (playwright-gate, typecheck) show FAILURE but PR is merged

**Root cause:** The coder's SOUL.md or inline script uses `gh pr merge --merge`
instead of setting auto-merge. The branch protection requires CI checks but
`gh pr merge --merge` can bypass them if the PR already has an approving review
(required reviews are not configured on some repos).

**Prevention:** The coder MUST:
1. Create PR with `--label "kanban:$HERMES_KANBAN_TASK"`
2. Enable auto-merge: `gh pr merge --auto --squash "$BRANCH"`
3. Verify CI is green BEFORE handoff:
   ```bash
   FAILING=$(gh pr view "$BRANCH" --json statusCheckRollup --jq '[.statusCheckRollup[] | select(.conclusion=="FAILURE")] | length')
   [ "$FAILING" -gt 0 ] && kanban_block(reason="CI not green: $FAILING checks failing")
   ```
4. Block with `review-required` — let the reviewer + CI watchdog handle the rest

**Real case (2026-05-28):** PR #170 on shop — merged by Seven74AI at 07:58 UTC with
build + playwright(1+2) + playwright-gate all FAILURE. No auto-merge enabled. Branch
protection requires `lint, typecheck, vitest, playwright-gate` with `strict: true`,
yet manual merge bypassed the playwright-gate failure.

## ⛔ CRITICAL: Tasks Created WITHOUT kanban-project-workflow → Red CI Merges

**This is the #1 root cause of red-CI merges.** When a coder task is created with
`skills=["shop"]` and no `kanban-project-workflow`, the coder agent has NO
knowledge of:
- Auto-merge only (`gh pr merge --auto --squash`)
- Never merge with red CI
- Kanban label requirement on PRs
- Reviewer gate requirement
- Branch protection enforcement

The coder implements the feature correctly, but then merges manually with
`gh pr merge --squash` — bypassing all CI gates. Broken code lands on main.

**Detection — find tasks missing the workflow skill:**
```sql
SELECT id, skills, status, title
FROM tasks
WHERE assignee='coder'
AND status NOT IN ('done','archived')
AND (skills IS NULL OR skills NOT LIKE '%kanban-project-workflow%');
```

**Backfill — fix all non-done coder tasks:**
```sql
UPDATE tasks SET skills='["<project>", "kanban-project-workflow"]'
WHERE assignee='coder' AND status NOT IN ('done','archived')
AND (skills IS NULL OR skills NOT LIKE '%kanban-project-workflow%');
```

**Prevention — ALWAYS include kanban-project-workflow in task creation:**
```bash
hermes kanban --board <board> create --assignee coder \
  --skills <project> --skills kanban-project-workflow ...
```

**Prevention — branch protection hardening:** Even with the right skills,
coders can still bypass checks if `enforce_admins: false`. See
`references/branch-protection-hardening.md` for the hardening procedure.

**Real case (2026-05-28):** Shop board — 10 coder tasks created with
`skills=["shop"]` only. Within 2 hours, 7 PRs merged with `build: FAILURE`,
`playwright-gate: FAILURE`. Root cause: missing `kanban-project-workflow` skill.
Branch protection `enforce_admins: false` let Seven74AI bypass. Fixed by:
(1) backfilling skills on all tasks, (2) setting `enforce_admins: true` +
`required_reviews: 1` on the fork's branch protection.

### The "Pre-Existing" Rationalization Trap

Even WITH `kanban-project-workflow` loaded, coders can rationalize red CI as
"not my fault" and use `gh pr merge --admin` to bypass. Common patterns:

- "Build fails on Fly token — pre-existing, not my code"
- "Playwright flaky — pre-existing on main, I didn't break it"
- "Lint/vitest pass, only pre-existing failures remain — safe to merge"

**This is NEVER acceptable.** Any red check, regardless of origin, means broken
code lands on main. The coder's job is to FIX the failure, not judge whether it's
their fault. The absolute rule at the top of this skill exists specifically to
counter this rationalization.

**Real case (2026-05-28):** PR #237 on shop — coder heartbeat: "build FAIL (Fly
token pre-existing), playwright FAIL (pre-existing flaky). Reviewer approved.
Planning admin-merge." Merged despite `enforce_admins: true`. The coder
rationalized pre-existing failures and bypassed. Fix: absolute rule added at
SKILL.md top + `enforce_admins: true` on branch protection.

## ⛔ Pitfall: Research Done ≠ Recommendations Addressed (Audit Follow-Through Gap)

When a researcher completes an audit or report with actionable recommendations,
the research task being `done` does NOT mean the recommendations were turned into
implementation tickets. This is the #1 silent gap in the pipeline — research
completes cleanly but 7-10 recommendations sit unaddressed for days.

**Why it happens:**
- Researcher produces a report in a kanban comment or workspace file
- Researcher completes with summary referencing "7 recos, 2 bugs, 5 improvements"
- Nobody (orchestrator, planner, or user) systematically checks: "did every reco become a ticket?"
- The research task looks done on the board — recommendations are invisible

**Symptoms:**
- Audit/report tasks marked `done` with summaries like "11 recommendations, 3 HIGH-priority"
- Searching the board for keywords from those recommendations returns zero implementation tickets
- Weeks pass, nobody notices the gap

**Detection — cross-reference research outputs with tickets:**
```bash
# 1. Find all researcher tasks with recommendations in their summary
hermes kanban --board <board> list | grep researcher | while read line; do
  tid=$(echo "$line" | awk '{print $2}')
  summary=$(hermes kanban --board <board> show "$tid" 2>&1 | grep "Latest summary:" -A1 | tail -1)
  if echo "$summary" | grep -qiE "recommand|recommend|ticket|P0|P1|HIGH|MEDIUM"; then
    echo "$tid: $summary"
  fi
done

# 2. For each recommendation keyword, check if any coder ticket exists
#    (manual — read the research comment, extract keywords, grep board)
```

**Prevention — after ANY research/audit task completes:**
1. Read the researcher's comment/summary — extract actionable recommendations
2. Check the board for corresponding implementation tickets (grep keywords)
3. Create any missing tickets immediately — don't wait for the next session
4. Comment on the research task: "Verified: N tickets created from recommendations"

**Bulk creation pattern** (when 5+ tickets are missing):
```python
from hermes_tools import terminal
for t in tickets:
    body = t["body"].replace("'", "'\\''")
    title = t["title"].replace("'", "'\\''")
    cmd = (
        f"hermes kanban --board <board> create "
        f"--assignee coder --priority {t['priority']} "
        f"--skill <project> --skill kanban-project-workflow "
        f"--body '{body}' '{title}'"
    )
    terminal(cmd)
```

**Real case (the-swarm 2026-05-29):**
- Timing audit (t_283c924e): 7 recommendations, 0 tickets created — gap discovered hours later
- Phase 4 space validation (t_3f68adc2, May 19): 3 HIGH-priority recos, 0 tickets — gap undiscovered for 10 days
- 10 missing tickets created in a single batch via execute_code

## ⛔ Pitfall: `active_pr` Respawn Guard Blocks Coder After Reviewer Unblock

When the coder posts a handoff comment containing a PR URL (`github.com/.../pull/N`),
the `active_pr` respawn guard prevents the task from spawning for **24 hours**.
This is correct behavior during the review phase (avoid creating duplicate PRs),
but it breaks the workflow when the reviewer approves the PR and the coder
needs to respawn to verify the merge.

**The cycle:**
1. Coder creates PR, enables auto-merge, posts handoff comment with PR URL
2. Coder blocks with `review-required`
3. Reviewer approves, unblocks the coder
4. Coder tries to spawn → `active_pr` guard blocks it (PR URL in comment < 24h)
5. If auto-merge is blocked (CI red, review not counting), nobody fixes it
6. Task stays `ready` with 20+ `respawn_guarded` events, PR stays open

**Symptoms:**
- `hermes kanban events <task>` shows repeated `respawn_guarded: active_pr`
- Task is `ready` but dispatcher refuses to spawn — 20+ attempts in logs
- PR is open with auto-merge enabled but `mergeStateStatus: BLOCKED`

**Immediate fix — delete the PR URL comment:**
```python
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
db.execute("DELETE FROM task_comments WHERE task_id='<task_id>' AND body LIKE '%github.com%pull%'")
db.commit()
print(f'Deleted {db.total_changes} PR URL comments')
db.close()
```

**Prevention — coder MUST fix CI BEFORE blocking for review:**
The root cause is blocking with red CI. If CI is green when the coder blocks,
the auto-merge completes without needing the coder to respawn. The CI watchdog
detects the merge and completes the task. The `active_pr` guard is never
triggered because the coder doesn't need to respawn.

This is enforced in the coder step-by-step (§ 3): verify CI is ALL GREEN
before creating the reviewer and blocking. Red CI → fix → re-run → only
block when green.

**Prevention — CI watchdog should clear PR URL comments on merge:**
When the CI watchdog detects a merged PR, it should delete the PR URL
comment from the coder task to clear the guard for future runs.

Real case: shop t_541d2c3a (2026-05-28) — 20 `respawn_guarded: active_pr`
events from 22:02 to 22:22. PR #238 auto-merge blocked (review not counting),
coder couldn't respawn to fix it. Fixed by deleting the PR URL comment.

**Symptoms:** Tasks sit `ready` for hours with repeated `respawn_guarded` events.
`hermes kanban events <task>` shows `respawn_guarded: active_pr`.

**Fix:** Delete the PR URL comment after merge. The CI watchdog does this
automatically. For manual cleanup:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
conn.execute(\"DELETE FROM task_comments WHERE body LIKE '%github.com%pull%'\")
conn.commit()
print(f'Deleted {conn.total_changes} comments')
conn.close()
"
```

**Guard system details** (from `check_respawn_guard()` in `kanban_db.py`):
Three checks in priority order — first match wins:
1. `blocker_auth` — last failure was 429/403/401/5xx (retry won't help)
2. `recent_success` — completed run within 1 hour (avoid duplicate work)
3. `active_pr` — PR URL in a comment within 24 hours (avoid duplicate PRs)

The guard is **stateless** — re-evaluated fresh every tick. When the condition
clears, the task spawns normally.

## Pitfall: Missing Kanban Labels on PRs — How to Detect and Backfill

PRs created without `--label "kanban:$HERMES_KANBAN_TASK"` are invisible to the CI watchdog.
The watchdog can't map them to kanban tasks, so even if they merge, the coder task stays blocked.

**Symptoms:**
- PR exists with no label starting with `kanban:`
- CI watchdog never unblocks the corresponding task
- Task stays `blocked` with `review-required` forever

**Audit — find unlabeled PRs:**
```bash
gh pr list --repo <repo> --state open --json number,labels --jq \
  '.[] | select([.labels[].name | select(startswith("kanban:"))] | length == 0) | .number'
```

**Backfill — add correct labels (open PRs only, merged/closed can't be edited):**
```bash
# Per-PR: gh pr edit <N> --repo <repo> --add-label "kanban:<task_id>"
# Per-PR via API: gh api repos/<repo>/issues/<N>/labels -X POST -f "labels[]=kanban:<task_id>"
# Replace old label: DELETE /labels/<old> then POST new
```

**Prevention:** Coder SOUL.md MUST include `--label "kanban:$HERMES_KANBAN_TASK"` in the
`gh pr create` command. The `kanban-project-workflow` skill shows the correct command;
verify the SOUL.md matches it.

**Real case (2026-05-28):** 5 of 12 open shop PRs had no kanban label. The coder
SOUL.md's `gh pr create` command was missing `--label`. Fixed by patching SOUL.md
and backfilling labels via `gh api` on open PRs. Merged/closed PRs (#170, #207)
were left unlabeled since they can't be edited.

## Technique: Splitting Sequential Ticket Chains into Parallel Chains

When you have a long batch of chained tickets (e.g., 12 PR fix tickets chained
with `--parent`), you can split them into 2+ parallel chains to double throughput.
Each chain processes independently — useful when `max_spawn > 1`.

**Procedure:**
```sql
-- 1. Find the midpoint of the chain via task_links
SELECT parent_id, child_id FROM task_links WHERE parent_id IN (SELECT id FROM tasks WHERE status='todo');

-- 2. Delete the link at the split point
DELETE FROM task_links WHERE parent_id='<last_of_chain_A>' AND child_id='<first_of_chain_B>';

-- 3. Promote the first ticket of chain B to ready
UPDATE tasks SET status='ready' WHERE id='<first_of_chain_B>';
```

**Constraints:**
- Chain B's tickets must already be in correct parent-child order via task_links
- Only delete one link — the rest of chain B inherits its internal chain correctly
- `max_spawn` must be ≥ number of parallel chains (coder: 3)
- Works because `todo` tasks auto-promote to `ready` when their parent completes

**Real case (2026-05-28):** 12-ticket shop batch split into chain A (6 tickets) and
chain B (4 tickets) by unlinking `t_c742820e` from parent `t_59ad6381`. Both chains
running simultaneously on coder profile (max_spawn=3).

**Symptom:** All kanban tasks on a board are `done`/`archived`, but many PRs remain open with red CI.
The PR was never merged — the ticket went `done` without merge verification.

**⚠️ Root cause (confirmed 2026-05-27):** The block watchdog (`check-blocked-tasks.py`)
explicitly does NOT unblock review-required tasks — it marks them as "review-blocked
(no auto-retry)". The watchdog only handles crash-retry (backoff: 2m→4m→6m→8m→10m).
The actual cause was a **manual bulk archive** — 25 tasks archived at the same
second (2026-05-24 14:34 UTC), with no `completed` or `archived` event recorded.
This bypasses the normal workflow entirely.

**Detection — find phantom-done tasks (archived without merge):**
```sql
-- Tasks archived without a completed event (direct status change)
SELECT t.id, t.title, t.completed_at
FROM tasks t
WHERE t.status IN ('done', 'archived')
AND t.completed_at IS NOT NULL
AND NOT EXISTS (
  SELECT 1 FROM task_events e 
  WHERE e.task_id = t.id 
  AND (e.kind = 'completed' OR e.kind = 'archived')
)
ORDER BY t.completed_at DESC;
```

**Detection — bulk archive at same timestamp:**
```sql
-- Tasks sharing the same completed_at timestamp (batch operation)
SELECT completed_at, COUNT(*) as cnt, GROUP_CONCAT(id, ', ') as tasks
FROM tasks
WHERE status IN ('done', 'archived')
GROUP BY completed_at
HAVING cnt > 5
ORDER BY completed_at DESC;
```

**Cross-reference kanban done tickets with GitHub open PRs:**
```bash
# List open PRs with kanban labels
gh pr list --repo Seven74AI/shop --state open --json labels,number,title \
  --jq '.[] | select(.labels[].name | startswith("kanban:")) | "#\(.number) \(.labels[].name) \(.title)"'

# For each, check if the kanban task is done
for pr in $(gh pr list --repo Seven74AI/shop --state open --json number --jq '.[].number'); do
  label=$(gh pr view $pr --repo Seven74AI/shop --json labels --jq '.labels[].name | select(startswith("kanban:"))')
  [ -n "$label" ] && echo "PR #$pr → $label ($(hermes kanban --board shop show ${label#kanban:} 2>&1 | grep 'status:'))"
done
```

**Prevention — NEVER bulk-archive/complete kanban tasks without verifying PR merge.** 
If a cleanup is needed, first cross-reference with open PRs. Archived tasks with
open PRs are invisible — no watchdog monitors them, no coder will fix them.

**Prevention — coder respawn MUST verify merge before completing:**
```bash
gh pr view $PR --repo $REPO --json mergedAt,state
# mergedAt must be non-null before kanban_complete()
```

Real case: shop board (2026-05-27) — 368 tasks all `done`/`archived`, 25 of them
bulk-archived at the exact same second (14:34 UTC May 24) with no completion event,
12 PRs still open with red CI. #224, #223, #216, #211, #210, #207, #206, #202, #187,
#181, #170, #226 all unmerged. Common failures: typecheck, build, vitest cascading.

The kanban block watchdog has **no bridge to GitHub**. If you manually merge a
PR, the kanban task stays `blocked` and the watchdog keeps escalating (every 5 min).

**ALWAYS complete the kanban task after a manual merge:**
```bash
hermes kanban --board <board> unblock <task_id>
hermes kanban --board <board> complete <task_id>
```

Also check child tasks — they may be `ready` and waiting on the completed parent.

## Pitfall: Profile Skill Management — Selective, NOT Sync-All

Skills live in the main profile's `skills/` directory. Kanban workers use their
own profile copies at `~/.hermes/profiles/<name>/skills/`.

**Philosophy: reduce to what each role actually needs.** 128 skills in a worker
profile is noise — every skill in the `available_skills` block costs tokens every
turn. Only 5-13 skills are actually used across all kanban tasks (see
`references/profile-skill-audit.md` for the real usage data). A reviewer doesn't
need `arxiv` or `polymarket`. A coder doesn't need `kanban-velocity` or
`hermes-journal`.

**Sync strategy: role-based, not blanket.**

1. Every profile gets the core: `kanban-worker`, `kanban-project-workflow`
2. **Exception:** `planner` gets `kanban-orchestrator` instead of `kanban-worker` — it never implements code
3. Every profile gets the project skills for its boards — **physical copies, not just on-demand.** The planner uses `HERMES_TENANT` → `skill_view()` to load the right project skill at runtime, but coders and reviewers need the SKILL.md file physically present in their profile (`--skills shop` is hardcoded in the task, not resolved from tenant). `HERMES_TENANT` is metadata only — it does NOT auto-inject skills.
4. Beyond that, each role gets ONLY what it uses:

| Role | Extra skills |
|------|-------------|
| `coder` | `tdd`, `systematic-debugging`, `github-pr-workflow`, `requesting-code-review`, `project-ci`, `long-running-tests`, `disk-cleanup`, `codebase-inspection`, `subagent-driven-development`, `writing-plans` |
| `reviewer` | `github-code-review`, `github-pr-workflow`, `systematic-debugging`, `codebase-inspection`, `project-ci`, `requesting-code-review` |
| `researcher` | `arxiv`, `blogwatcher`, `llm-wiki` (if needed) |
| `planner` | `kanban-orchestrator`. Core: `kanban-project-workflow`, `writing-plans` (NOT `kanban-worker`). Project skills (shop, the-swarm, etc.) loaded on-demand via `HERMES_TENANT` → `skill_view()`. Personality: `technical`. |
| `hermes-devops` | `kanban-ci-watchdog`, `kanban-velocity`, `kanban-profile-blueprint`, `hermes-journal`, `disk-cleanup`, `webhook-subscriptions`, all `github-*`, `renovate-bulk-merge`, `hermes-agent`, `project-ci`, `long-running-tests` |

External skill suites (Matt Pocock, etc.) are added only to roles that benefit:
`coder` might get `tdd`, `diagnose`, `triage`; `reviewer` might get `diagnose`;
`researcher` and `planner` typically don't need them.

**Dogfood project skills — loaded on-demand via tenant, NOT physically synced.**

The tenant auto-injection (see below) eliminates the need to physically sync
dogfood SKILL.md files to every worker profile. When a task carries `--tenant shop`,
the dispatcher resolves the skill from `~/.hermes/skills/` at spawn time.
**Do NOT bulk-sync dogfood skills into all profiles** — they waste tokens in
the `available_skills` block. Only the `planner` profile needs them pre-synced
(because it uses `skill_view()` on-demand, not `--skills`).

The sole exception: new dogfood project skills must be synced to the `planner`
profile immediately (`cp -r` the whole skill directory).

**To sync a skill to specific profiles (NOT all):** use `rsync -a --delete` — it
handles directories, references, scripts, and cleans stale files that `cp -r` leaves behind:

```bash
for p in coder planner; do
  rsync -a --delete \
    /root/.hermes/skills/<category>/<skill-name>/ \
    /root/.hermes/profiles/$p/skills/<category>/<skill-name>/
done
```

**After updating the source skill, sync to all profiles that have a copy:**

**Pitfall: `rsync --delete` overwrites profile-local changes silently.** Before
syncing, diff first to see what would be lost:
```bash
diff -r ~/.hermes/skills/<category>/<skill>/ ~/.hermes/profiles/<profile>/skills/<category>/<skill>/
```
Profile copies may have intentional divergences (SOUL.md instructions, custom
references, different defaults). Review the diff before running `rsync --delete`.

**Pitfall: Nested duplicate skill directory from rsync — "Unknown skill(s)" crash-loop.** When the target directory already exists, `rsync -a --delete source/ target/` copies the source directory INSIDE the target instead of replacing its contents, creating a nested duplicate like `target/skill-name/SKILL.md` alongside the original `target/SKILL.md`. This is a **trailing-slash trap**: `rsync ... source/ target` (no trailing slash on target) copies source into target, while `rsync ... source/ target/` (trailing slash on both) merges contents correctly.

**Symptoms:**
- Worker starts and dies in ~60s (startup time) — consistent crash at the 1-minute mark
- `hermes kanban log <task>` shows "Error: Unknown skill(s): <name>" repeated
- `tail errors.log` shows `WARNING tools.skills_tool: Skill name collision for '<name>': 2 candidates`
- Task diagnostics show `consecutive_crashes=N` climbing rapidly with `pid X not alive` or `pid X exited with code 1`
- The skill appears in `hermes skills list` (from the main profile) but the worker can't load it due to collision

**Detection:**
```bash
find /root/.hermes/profiles/<profile>/skills/ -mindepth 2 -name "SKILL.md" -path "*/<skill-name>/<skill-name>/SKILL.md"
```

**Fix:**
```bash
# Remove the nested duplicate subdirectory
rm -rf /root/.hermes/profiles/<profile>/skills/<category>/<skill-name>/<skill-name>/
# Then reclaim crashed tasks
hermes kanban --board <board> reclaim <task_id>
```

**Prevention:** Always use trailing slashes on BOTH source and target in rsync commands:
```bash
# ✅ CORRECT — merges contents, doesn't nest
rsync -a --delete /root/.hermes/skills/<category>/<skill>/ /root/.hermes/profiles/<p>/skills/<category>/<skill>/

# ❌ WRONG — copies source into target, creates nested duplicate
rsync -a --delete /root/.hermes/skills/<category>/<skill>/ /root/.hermes/profiles/<p>/skills/<category>/<skill>
```

**Real case (hermes-ops 2026-05-25):** Reviewer profile had `kanban-project-workflow/kanban-project-workflow/SKILL.md` nested inside the skill directory. Both reviewer tasks (t_e9e783a1, t_0c9c3182) crash-looped for 25h — 208 and 318 runs respectively, all dying in ~60s with "Unknown skill(s): kanban-project-workflow". The block watchdog escalated as "Reviewer profile systemic crash — 25h outage."

```bash
for p in researcher researcher-videos coder reviewer planner; do
  [ -d "/root/.hermes/profiles/$p/skills/<category>/<skill-name>" ] && \
    rsync -a --delete \
      /root/.hermes/skills/<category>/<skill-name>/ \
      /root/.hermes/profiles/$p/skills/<category>/<skill-name>/
done
```

**Dispatcher tenant auto-injection (safety net, 2026-05-22):** The dispatcher now
auto-resolves `--tenant <name>` into `--skills <name>` at spawn time. When a task
has `tenant=shop`, the dispatcher searches `~/.hermes/skills/` for a matching
skill, syncs it into the worker profile if missing, and injects `--skills shop`.
This means tasks no longer need the project skill listed explicitly — the tenant
is enough. The auto-injection is a defence-in-depth measure; tasks with
`--skills shop` still work fine (dedup prevents double-loading).

Missing profile copies cause "Unknown skill(s): <name>" crashes on worker spawn.
If a task's `--skills` references a skill not in the worker's profile, the spawn
fails. The pre-spawn watchdog only scans `ready` tasks for NO-SKILLS (NULL/empty)
— it does NOT detect skills that exist in the main profile but are missing from
the worker's profile copy. The only symptom is the dispatch error log.
**The tenant auto-injection above eliminates this class of error for project
skills, but only when tasks carry `--tenant`.**

**Pre-spawn watchdog blind spot:** a task with `skills=["shop", "kanban-project-workflow"]`
passes the NO-SKILLS check because the column is non-NULL. But if `shop` was
removed from the `coder` profile during a skill-curation pass, every coder task
with `--skills shop` will crash on dispatch with "Unknown skill(s): shop".
The pre-spawn watchdog never sees this — it's a profile-level gap, not a
task-level gap. Audit profile skill coverage with:

```bash
# List dogfood skills a profile is missing
for ds in shop the-swarm music-library videogame-lab baguette glance; do
  [ -d "/root/.hermes/profiles/coder/skills/dogfood/$ds" ] || echo "MISSING: $ds"
done
```

**Pitfall: new dogfood project skill → sync to ALL profiles before creating tasks.**
When you create a SKILL.md for a new board (e.g. `edgee-lab`), sync it to
`coder`, `reviewer`, `planner`, `researcher`, and `hermes-devops` profiles
immediately. Any task with `--skills <new-skill>` will fail on dispatch until
the profile copy exists.

## Worker Tuning

### `max_iterations` vs `max_turns` — TWO config keys, `max_turns` is the one that matters

**⚠️ PITFALL: `max_turns` (root-level) is the actual iteration limit for kanban workers, NOT `kanban.max_iterations`.** The task error message says "Iteration budget exhausted (90/90)" — this comes from `max_turns`, not `kanban.max_iterations`. Setting only `kanban.max_iterations: 120` does nothing if `max_turns` is still 90.

**Both must be set:**
```yaml
# Root-level — this is what actually limits kanban worker turns
max_turns: 120

# Kanban section — safety net, but secondary
kanban:
  max_iterations: 120
```

Set via:
```bash
hermes config set --profile <name> max_turns 120
hermes config set --profile <name> kanban.max_iterations 120
```

Default 50-90 causes "Iteration budget exhausted" on complex tasks (e2e test runs,
migrations, multi-file refactors). A typical shop coder task uses ~40 turns just for
setup (clone, pnpm install, prisma generate, first typecheck), leaving only 50 turns
for actual debugging and fixing — insufficient for anything beyond 1-2 trivial errors.

**Real case (2026-05-28):** Coder tasks on shop board hit 90/90 turns despite
`kanban.max_iterations: 120` being set. Root cause: `max_turns: 90` was the active
limit. Fixed by setting `max_turns: 120` on the coder profile.

### `max_runtime_seconds` — per-task DB column, set to 3600s

The profile's `max_runtime_seconds` does NOT flow to kanban tasks. Each task
has its own column in kanban.db. **Heartbeat is the primary liveness signal.**
Set `max_runtime_seconds = 3600` (1h) as a safety net for runaway loops.

```bash
python3 -c "
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
db.execute(\"UPDATE tasks SET max_runtime_seconds = 3600 WHERE max_runtime_seconds IS NULL OR max_runtime_seconds < 3600\")
db.commit()
print(f'Updated {db.total_changes} tasks')
db.close()
"
```

**Pitfall: NULL means NO time limit.** `enforce_max_runtime()` in `kanban_db.py:3878`
filters `WHERE max_runtime_seconds IS NOT NULL`. Tasks with NULL
`max_runtime_seconds` are **never checked for timeout**. They can run
indefinitely — only the stale-heartbeat check (4h no heartbeat) reclaims them.
Always create tasks with `--max-runtime 3600` or backfill via SQL above.

## Closing Upstream Issues After Work Completes

The kanban pipeline (Researcher → Planner → Coder → Reviewer → Done) tracks
implementation, but the upstream GitHub issues that motivated the work are a
**separate lifecycle**. Kanban tasks can all be `done` while upstream issues
remain `open` — the two are not coupled.

**After a consolidation PR merges to upstream, close the corresponding
upstream issues.** This is manual. No kanban automation bridges the gap.

### Token permissions (fork model)

Closing issues on upstream (`mnlamart/<repo>`) requires write access to that repo:

| Token | Can close? | Notes |
|-------|-----------|-------|
| Seven74AI (coder) | ❌ 403 | `repo` scope, but not a collaborator on upstream |
| hermes-sevenai-reviewer (GitHub App) | ❌ 403 | Has Contents + PR write; lacks Issues: Write |
| mnlamart personal token | ✅ | Full owner access to upstream |

The GitHub App can be granted Issues: Write in its installation settings on
upstream repos, avoiding the need for a personal token.

### Bulk-close recipe (when token is available)

```bash
TOKEN="<mnlamart or app token with issues:write>"
for n in $(seq <first> <last>); do
  curl -s -X PATCH \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/<owner>/<repo>/issues/$n" \
    -d '{"state":"closed","state_reason":"completed"}'
done
```

`gh issue close` works too, but requires the authenticated user to have push
access — same permission constraint applies.

### When to close

- After a consolidation PR merges (fork → upstream): close all issues whose
  work was included in that consolidation.
- After a direct-model PR merges (no upstream fork): close the issue immediately.
- Don't close issues prematurely — only when the code is on upstream main and
  CI is green.

Real case: shop board (2026-05-22) — 262 kanban tasks done, consolidation PR #198
merged 226 commits to upstream, but all 66 upstream issues (#101–#167) remained
open. Seven74AI and the reviewer app both got 403 on close.

## Pitfall: Stale PRs from Out-of-Order Slice Merges

When later vertical slices get merged before earlier ones (e.g., Slice 4 + 5
merged, but Slice 1 + 3 PRs still open), the open PRs may be **fully obsolete**
— not just conflicting, but entirely superseded by code already on main.

**Symptoms:**
- PR shows `mergeable: CONFLICTING` on files that already exist in main
- `git diff --name-only` shows files that main already contains (often with MORE functionality)
- Diff of PR branch vs main shows the PR has a SUBSET of main's code

**Detection — before attempting rebase, check if the PR is obsolete:**
```bash
# 1. List files the PR touches vs files already on main
comm -12 <(git diff --name-only merge-base..pr-branch | sort) \
         <(git ls-tree -r --name-only origin/main | sort)

# 2. For key files, diff PR version vs main version
diff <(git show pr-branch:path/to/file.ts) <(git show origin/main:path/to/file.ts)

# 3. If main has the SAME or MORE code → PR is obsolete, close it
```

**Cleanup:**
```bash
gh pr close <N> --repo <repo> -c "Closed: obsolete — functionality already in main via later slices."
gh api -X DELETE repos/<repo>/git/refs/heads/<branch>
```

**Real case (2026-05-29):** the-swarm PRs #48 (Slice 1) and #49 (Slice 3) were
both obsolete — Slice 4 and 5 had been merged out of order, and main already
contained the same files with more functionality. Every file in PR #49 existed
identically in main; PR #48's flat prestige fields had been superseded by main's
`prestige` object + `prestigeTree`. Both closed + branches deleted.

## PR Obsolescence Detection

When open PRs have merge conflicts, first check if the PR is **still legitimate**
(new code not already in main via a different merge path). Parallel slices, squash-merges,
and refactors can make older PRs obsolete without anyone noticing.

See `references/pr-obsolescence-detection.md` for the full procedure: check branch
existence, compare files against main, diff for superset/subset, cleanup.

## Batch Ticket Creation

When decomposing a research report into 10+ implementation tickets, use the
`execute_code` loop pattern instead of creating tickets one at a time via CLI.

See `references/batch-ticket-creation.md` for the template.

## PR Consolidation

When multiple open PRs overlap (e.g., dep bumps + CI fixes + migration),
consolidate into one PR:

1. Check which PRs are already merged on main (`gh pr view` + `git log`)
2. Apply remaining changes onto a single branch off main
3. Run full local CI in background + wait
4. Push to fork, create a single consolidated PR
5. Close superseded PRs with comment
6. Close upstream issues corresponding to the consolidated work (see § Closing Upstream Issues)

## ⛔ Pitfall: Reviewer App Approval Not Counting (`authorAssociation: NONE`)

**Root cause: The GitHub App has `contents: read` — it needs `contents: write`.**

When the app only has `contents: read`, its reviews show `authorAssociation: "NONE"`
and do NOT count toward branch protection's `required_reviews`. This blocks auto-merge
even when all CI is green and the reviewer approved.

**Symptom:** `mergeStateStatus: "BLOCKED"` with 1 APPROVED review, all CI green.
```bash
gh pr view N --repo <repo> --json reviews --jq '[.reviews[] | {state, authorAssociation}]'
# authorAssociation: "NONE" → review doesn't count
```

**Check current app permissions (requires app private key):**
```bash
python3 -c "
import jwt, time, requests
with open('/root/.hermes/profiles/reviewer/home/.config/hermes-sevenai-reviewer.pem','rb') as f:
    pk = f.read()
jwt_tok = jwt.encode({'iat':time.time()-60,'exp':time.time()+600,'iss':'3788528'}, pk, algorithm='RS256')
r = requests.get('https://api.github.com/app/installations/134194993',
    headers={'Authorization':f'Bearer {jwt_tok}','Accept':'application/vnd.github+json'})
print(r.json()['permissions'])
"
# Look for "contents": "read" → this is the problem
```

**Permanent fix — change app permissions in GitHub UI:**
1. Go to GitHub → Settings → Developer settings → GitHub Apps → hermes-sevenai-reviewer
2. Permissions & events → Repository permissions → Contents
3. Change from "Read-only" to **"Read & write"**
4. Save changes → accept the installation update prompt

✅ **Fix applied 2026-05-29.** The app now has `contents: write`. Reviews count correctly —
verify with `reviewDecision` (not `authorAssociation` — `NONE` is cosmetic and doesn't prevent merging):
```bash
gh pr view N --repo <repo> --json reviewDecision,mergeStateStatus
# reviewDecision: "APPROVED" → review counts
# mergeStateStatus: "BLOCKED" → something else is wrong
```

**Scope:** This affects ALL repos where the app is installed — shop, music-library,
the-swarm, videogame-lab. The app had `contents: read` from creation until 2026-05-29.

Real case: shop#238 (2026-05-28) — `mergeStateStatus: BLOCKED` despite APPROVED review
and all-green CI. Root cause: `contents: read` → `reviewDecision: REVIEW_REQUIRED`.
Fixed by upgrading to `contents: write`.

## Pitfall: CI Status Check Names vs Branch Protection Required Contexts

GitHub requires **exact match** between CI job context names and branch protection
required contexts. Two common mismatches:

### Emoji `name:` fields
```yaml
# WRONG — reports context "⬣ ESLint", branch protection expects "lint"
lint:
  name: ⬣ ESLint
```
**Fix:** Remove job-level `name:` fields. The YAML key (`lint:`) becomes the context.

### Matrix sharding
```yaml
# Reports "playwright (1)" and "playwright (2)" — doesn't match "playwright"
playwright:
  strategy:
    matrix:
      shard: [1, 2]
```
**Fix:** Gate job (see § Playwright E2E Sharding Standard in `kanban-profile-blueprint`).

**Audit command:**
```bash
# Required contexts vs actual CI job names
gh api repos/<repo>/branches/main/protection --jq '.required_status_checks.contexts[]'
gh pr checks <N> --repo <repo>
```
Found on shop + music-library (2026-05-21). Documented in `kanban-profile-blueprint`.

## Standard Pipeline

All project boards follow the same role pipeline:

```
Researcher → Planner (PRD + to-issues) → Coder → Reviewer → Done
```

- **Researcher:** Investigate, compare approaches, produce recommendations.
  Handoff: `kanban_complete(summary=..., metadata={recommendation, benchmarks})`.
  **Deliverable by board type:**
  - **Project boards (shop, the-swarm, etc.)** — post results as a comment on the
    originating GitHub issue (e.g. `gh issue comment N --repo <repo> --body "..."`).
    The kanban task summary is ephemeral (workspace GC'd); the GitHub issue is durable.
  - **Ops boards (hermes-ops, hermes-skills)** — no GitHub repo. Post the full
    analysis as a **kanban comment** + create follow-up tickets for P0/P1 items.
    Do NOT write deliverables to the Obsidian vault — the kanban board IS the
    authoritative record for ops work.
- **Planner:** Generate PRD via `to-prd` skill, then decompose into vertical slice
  tickets via `to-issues` skill. Handoff: PRD + child tasks as tracer-bullet slices.
  Each slice traverses ALL layers (DB → logic → UI → tests) and is independently
  verifiable. Tasks are classified HITL (Human In The Loop) or AFK (Away From Keyboard).
- **Coder:** First, explore the codebase with `skill_view("zoom-out")` to understand existing patterns and module interfaces. Then implement, test, open PR, enable auto-merge, create reviewer task, block. Handoff: PR auto-merge enabled, reviewer task created with codebase exploration findings.
- **Reviewer:** Pull PR diff, review code, approve or request changes. Approve
  unblocks auto-merge; request-changes requires coder fix + re-review.

All boards use the same unified PR workflow (CI + reviewer → auto-merge).
No per-board variation. Project-specific details (GitHub model, tech stack,
testing conventions) live in the project skill (`shop`, `the-swarm`, etc.).

### Anti-Specs-to-Code Guardrails

Our pipeline (Researcher → Planner → Coder → Reviewer) risks the "specs-to-code trap"
identified by Matt Pocock: a coder implements directly from the planner's vertical
slice ticket without understanding the existing codebase. The result is code that
"works" but doesn't fit — wrong patterns, duplicate abstractions, ignored conventions.

Matt's rule: **"le code reste le champ de bataille"** — the code is where the battle
is fought. Specs are a guide; the codebase is the source of truth.

**Proactive guardrails (applied BEFORE implementation, not caught in review):**

1. **Coder MUST explore the codebase before writing code:**
   - Load `zoom-out` skill: `skill_view("zoom-out")` — maps relevant modules and domain vocabulary
   - Use `delegate_task` for deeper analysis of related modules and patterns
   - Document findings in a kanban comment: key modules, patterns identified, conventions to follow

2. **Reviewer MUST check integration, not just correctness:**
   - "Does this code demonstrate understanding of existing patterns?" (not isolation)
   - "Does it follow existing conventions: naming, file structure, error handling?"
   - "Does it reuse existing abstractions rather than inventing new ones?"
   - If any fail → NEEDS CHANGES with specific file references showing the correct pattern

3. **PRD "Implementation Decisions" section should reference existing modules:**
   - The planner's `to-prd` output should name relevant modules and interfaces
   - This bridges the gap between abstract spec and concrete codebase
   - Coders use these references to start their exploration

**Why CI + review catches errors AFTER they're made (reactive), but codebase**
**exploration prevents them (proactive). Both are needed. CI gates correctness;**
**reviewer gates quality; codebase exploration gates fit.**

4. **Periodic architecture review (`improve-codebase-architecture`):**
   - Run on the project after enough work has accumulated to make shallowness visible
   - The skill produces an HTML report with deepening opportunities, Mermaid diagrams, and before/after visualizations
   - Prerequisites: `CONTEXT.md` (domain glossary) and `docs/adr/` (or `docs/decisions/`) must exist

### Architecture Review Triggers (improve-codebase-architecture)

The `improve-codebase-architecture` skill finds "deepening opportunities" — refactors
that turn shallow modules (interface nearly as complex as implementation) into deep
modules (large behaviour behind a small interface). It produces an HTML report with
Mermaid diagrams and before/after visualizations.

**When to trigger — Coder:**

| Trigger | Condition |
|---------|-----------|
| Module churn | 3-5 PRs merged touching the same module (e.g., `order.server.ts`, checkout flow) |
| Tight coupling felt | Working on a module and bouncing between 5+ files just to understand one concept |
| God module touched | PR touches `order.server.ts` (1309 lines), `misc.tsx` (20+ functions), or any file >800 lines |
| New domain concept | Adding a new domain entity — run before implementation to find the right seam |
| Ad-hoc | User asks "should we refactor this?" — run the skill instead of guessing |

**When to trigger — Reviewer:**

| Trigger | Condition |
|---------|-----------|
| Cross-module PR | PR touches files in 3+ distinct `app/utils/` modules or 2+ route areas |
| Shallow module pattern | PR adds a new file that's a thin pass-through (interface ≈ implementation) |
| Duplication detected | PR copy-pastes logic that already exists elsewhere (e.g., `getStoreAddress`, search/filter UI) |
| Post-merge cleanup | After a consolidation PR merges 20+ commits — run to catch accumulated shallowness |
| Periodic | Every ~30 merged PRs on a project board — schedule as a recurring task |

**Skill location:** `software-development/improve-codebase-architecture` — deployed to
`coder` and `reviewer` profiles. The skill uses the project's `CONTEXT.md` for domain
vocabulary and `docs/adr/` (or `docs/decisions/`) to avoid re-proposing rejected designs.

**Running the skill (coder or reviewer profile):**
```bash
skill_view("improve-codebase-architecture")
# Step 1: Explore — walk the codebase, note friction, apply deletion test
# Step 2: Generate HTML report to /tmp/architecture-review-<timestamp>.html
# Step 3: Grilling loop — user picks candidates, deepens interactively
```

**First-pass validation:** Shop project (2026-05-24) — found 10 candidates: 6 Strong,
2 Worth Exploring, 1 Speculative, plus 5 ADR-003-deferred carrier candidates.
Report: `/tmp/architecture-review-20260524.html`. Top recommendation: request-scoped
currency cache (1 file, 19 callers, zero interface change).

### Planner Pipeline: Grill → PRD → Issues

The planner's workflow has three phases:

```
Phase 1: grill-with-docs → to-prd (PRD Generation)
Phase 2: to-issues (Vertical Slice Decomposition)
Phase 3: kanban_create + Audit (Ticket Creation)
```

#### Phase 1: PRD Generation (`to-prd`)

After the researcher produces recommendations, the planner MUST generate a
formal PRD before creating implementation tickets. The PRD bridges "what to
build" and "how to build it" — giving the coder user stories, implementation
decisions, testing decisions, and out-of-scope boundaries.

**Step-by-step:**

1. **Load context** — `skill_view("grill-with-docs")` to interview/stress-test
   the plan against the project's domain model
2. **Generate PRD** — `skill_view("to-prd")` to synthesize the interview into a
   structured PRD using the template below
3. **Publish** — post the PRD to the project issue tracker with the
   `ready-for-agent` triage label (no additional triage needed)
4. **Handoff** — the PRD issue URL becomes the "Parent" reference in all
   child kanban tickets

**PRD publication mechanics:**

- The `to-prd` skill publishes via the project's configured issue tracker
  (GitHub `gh issue create`, GitLab `glab issue create`, or local markdown)
- Apply the `ready-for-agent` label — this signals that the PRD is fully
  specified and an AFK agent can pick it up
- Do NOT apply `needs-triage` — the PRD has already been triaged during
  grilling

#### PRD Template

Every PRD MUST contain these five sections. The template is defined in the
`to-prd` skill and reproduced here for reference:

```markdown
## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

This list of user stories should be extremely extensive and cover all aspects of
the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being
outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more
precisely than prose can (state machine, reducer, schema, type shape), inline
it within the relevant decision and note briefly that it came from a prototype.
Trim to the decision-rich parts — not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not
  implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.
```

**PRD quality rules:**

- User stories must be exhaustive — cover happy path, edge cases, error states,
  and all actor roles
- Implementation decisions should mention modules and interfaces but not file
  paths
- Testing decisions must reference prior art in the codebase (similar test
  files, patterns) so the coder knows where to look
- Out of Scope is mandatory — prevents scope creep during implementation
- The PRD is NOT a kanban task — it's a reference document that child tasks
  link back to

### Vertical Slice Ticket Guidelines

Since deployment of `to-issues` (2026-05-24), ALL new AFK kanban tasks MUST
use the vertical slice format:

```markdown
## Parent
PRD: [link or reference to the PRD ticket]

## What to build

[A concise description of this vertical slice. Describe the end-to-end BEHAVIOR,
not layer-by-layer implementation. Avoid specific file paths or code snippets
— they go stale fast.]

## Acceptance criteria

- [ ] Criterion 1 — independently verifiable
- [ ] Criterion 2 — demoable/screenshotable
- [ ] Criterion 3 — testable in isolation

## Blocked by

- None - can start immediately
```

**Vertical slice rules:**
- Each ticket traverses ALL layers (DB → logic → UI → tests)
- Each ticket is independently verifiable — a completed slice is demoable on its own
- Prefer many thin slices over few thick ones
- Prefer AFK over HITL
- Dependencies should be minimal — use "Blocked by" only for true blockers
- HITL slices require human interaction (architectural decisions, design reviews)
  and are created with `--triage` or `--blocked` status
- AFK slices can be implemented and merged without human interaction

**Anti-patterns to avoid:**
- Horizontal slices: "Build the database layer" / "Build the API layer" / "Build the UI"
- Multi-phase tickets: "Phase 1: setup, Phase 2: core, Phase 3: polish" in one ticket
- Layer-specific tickets: "Add the Prisma schema" (no UI, no tests, not verifiable alone)
- Analysis + implementation in one ticket: mixing research with coding

See `references/vertical-slice-example.md` for a worked example (Shop VAT/Tax feature)
showing how 5 vertical slices decompose a PRD into independently verifiable tickets.

### Gap Analysis Sub-Pipeline

When a big consolidation or bulk merge lands, a gap analysis is needed to detect
features that were marked "done" on the board but never reached upstream:

```
Researcher (gap audit) → Planner (ticket creation) → Coder (re-implement gaps) → Reviewer → Done
```

See `references/gap-analysis-workflow.md` for the full methodology (SQL query
kanban.db → grep upstream code → categorize LANDED/MISSING/PARTIAL).

### Recurring Task Templates

- **CI fix "0 flaky"** — `references/ci-fix-template.md` — task body + create command

## Status Checks: PRs + Kanban Multi-Board

Quick audit across all project boards — forks, upstream repos, and kanban tickets.
See `references/cross-repo-pr-status.md` for the one-liner pattern.

## Pitfall: Promoted Children Stuck as `scheduled`

When a coder creates a reviewer child and the parent is blocked, the child is
deferred as `scheduled`. The parent→child auto-promotion (`scheduled → ready`)
can silently fail when the parent completes. The task stays `scheduled` forever
— invisible to the dispatcher AND to the pre-spawn watchdog (which only scans
`ready`). Also invisible to the block watchdog (the task isn't `blocked`).

**Detection & fix:** see `references/scheduled-task-stuck.md`.

## Kanban DB Schema

Full column reference for the `tasks` table (and related tables) in
`references/kanban-db-schema.md`. Use this when writing SQLite queries against
kanban.db — column names, types, timestamp conventions, and common query patterns.
**No `updated_at` column** — use `started_at`, `completed_at`, or `last_heartbeat_at`.
**Heartbeat column is `last_heartbeat_at`**, not `heartbeat_at`.

### Pitfall: Default Board Uses Root DB

Most boards live at `/root/.hermes/kanban/boards/<slug>/kanban.db`. The **`default`**
board is the exception — it uses `/root/.hermes/kanban.db` at the repository root.
There is no `/root/.hermes/kanban/boards/default/` directory.

```bash
# Project boards
python3 -c "import sqlite3; db=sqlite3.connect('/root/.hermes/kanban/boards/shop/kanban.db')"

# Default board (KB, general tasks)
python3 -c "import sqlite3; db=sqlite3.connect('/root/.hermes/kanban.db')"
```

Glob patterns like `glob.glob('/root/.hermes/kanban/boards/*/kanban.db')` will NOT
match the default board. Include the root DB explicitly when scanning all boards.

## Pause/Resume All Boards

When the user wants to pause ALL kanban activity (maintenance, OOM, deployment):

### Pause

```bash
# 1. Kill all running worker processes
pkill -f "hermes.*kanban task" 2>/dev/null
ps aux | grep 'kanban/boards/.*workspaces' | grep -v grep | awk '{print $2}' | xargs -r kill 2>/dev/null

# 2. Block ALL non-done tasks on all active boards (via DB — faster than CLI per-task)
python3 -c "
import sqlite3, os, glob
for db_path in glob.glob('/root/.hermes/kanban/boards/*/kanban.db'):
    db = sqlite3.connect(db_path)
    n = db.execute(\"UPDATE tasks SET status='blocked' WHERE status NOT IN ('done','archived','blocked')\").rowcount
    if n: print(f'{os.path.basename(os.path.dirname(db_path))}: blocked {n}')
    db.commit()
    db.close()
"

# 3. Pause watchdogs (CRITICAL — they unblock tasks otherwise)
hermes cron pause 7ad8ddd5b9c9   # Kanban Block Watchdog
hermes cron pause 10cb5de254d0   # CI Watchdog (light)
```

### Resume

```bash
# 1. Resume watchdogs
hermes cron resume 7ad8ddd5b9c9   # Block watchdog
hermes cron resume 10cb5de254d0   # CI watchdog

# 2. Unblock specific tasks the user wants to work on
hermes kanban --board <board> unblock <task_id>

# 3. Dispatch
hermes kanban --board <board> dispatch
```

### Pitfall: Block Watchdog Unblocks Manual Blocks

Direct DB `UPDATE tasks SET status='blocked'` can be reverted by the block
watchdog (cron `7ad8ddd5b9c9`, every 5 min). The watchdog sees a blocked
task with no known blocker reason and unblocks it. **Always pause the
block watchdog BEFORE blocking tasks**, or use `hermes kanban block` with
## OOM Prevention

Multiple parallel kanban workers can exhaust memory on constrained VMs.
Each worker spawns heavy subprocesses: TypeScript tsserver (800MB-1GB RSS),
pnpm dev servers (200-500MB), playwright/vitest runners.

### Root causes

1. **Too many parallel workers** — `max_spawn` in config.yaml limits
   simultaneous dispatches. With `max_spawn=3`, at most 3 workers per
   profile run at once. But when multiple boards are active, the total
   can still exceed memory.
2. **TypeScript tsserver per workspace** — each worker clones the repo into
   its own workspace, each with its own `node_modules` and tsserver instance.
   A single tsc process can consume 838MB RSS.
3. **Orphaned workspace servers** — Vite dev servers, mock servers, and
   tsserver daemons from completed/crashed tasks accumulate. The workspace
   GC cron (every 15 min) cleans directories but not orphaned processes.
4. **No cgroup memory limit** — `MemoryMax=infinity` on the hermes-gateway
   systemd service. Set a limit: `systemctl set-property hermes-gateway MemoryMax=6G`.

### Detection

```bash
# Check cgroup memory
systemctl show hermes-gateway | grep -E 'Memory(Current|Peak|Swap)'

# Check OOM kills in dmesg
dmesg -T | grep -i 'oom.*killed' | tail -5

# Count stale workspace processes
ps aux | grep 'kanban/boards/.*workspaces' | grep -v grep | wc -l

# Current memory pressure
free -h
```

### Mitigation

- Keep `max_spawn` low (3 for coder, 2 for reviewer)
- Run `hermes kanban gc` periodically to clean workspace directories
- Kill orphaned workspace processes: `ps aux | grep 'kanban/boards/.*workspaces' | grep -v grep | awk '{print $2}' | xargs -r kill`
- Set a cgroup memory limit on the gateway
### Pre-Spawn Watchdog (automated)

A notification-only cron (`pre-spawn-watchdog.py`, every 5 min) scans all boards
for ready tasks with issues. It reports to Discord but takes NO action:

- `NO-SKILLS` — skills is NULL or empty
- `NO-MRT` — max_runtime_seconds is NULL
- `PR-URL-IN-BODY` — task body contains a github.com PR URL
- `PR-URL-COMMENTS(N)` — N comments contain github.com PR URLs  
- `NO-ASSIGNEE` — no assignee (expected for RECETTE bookmarks)

Silent when clean. Created 2026-05-20 (cron `ceead0ca5089`).

### Pre-Spawn False Positives: Gap-Recreated Tasks

When a planner recreates implementation tasks from a gap analysis, the new
tasks may carry stale PR URLs from the gap report. These trigger
`PR-URL-IN-BODY` / `PR-URL-COMMENTS` in the pre-spawn watchdog AND the
`active_pr` respawn guard — blocking dispatch.

**Cleanup after gap ticket creation:**

```python
import sqlite3
db = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')

# Delete PR URL comments
db.execute("DELETE FROM task_comments WHERE body LIKE '%github.com%pull%'")

# Strip PR URLs from task bodies (replace with benign marker)
import re
for row in db.execute("SELECT id, body FROM tasks WHERE body LIKE '%github.com%pull%'"):
    clean = re.sub(r'https?://github\.com/\S+', '[PR URL removed — pre-consolidation]', row[1])
    db.execute("UPDATE tasks SET body=? WHERE id=?", (clean, row[0]))

# Fix NULL skills and MRT
db.execute("UPDATE tasks SET skills='[\"shop\",\"kanban-project-workflow\"]' WHERE skills IS NULL")
db.execute("UPDATE tasks SET max_runtime_seconds=3600 WHERE max_runtime_seconds IS NULL")

db.commit()
db.close()
```

This is also covered in `references/cleanup-ready-tasks.md`.

### One-Shot Cleanup (manual, after major updates)

After creating/updating shared skills or changing profile configs, run a one-shot
cleanup to fix stale tasks that were created before the updates. See
`references/cleanup-ready-tasks.md` for the full script.

Fixes: NULL skills → set to board-appropriate skills list, NULL mrt → 3600,
PR URLs in bodies → replaced with text references.
