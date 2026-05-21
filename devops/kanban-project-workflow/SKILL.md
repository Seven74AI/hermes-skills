---
name: kanban-project-workflow
description: "Shared kanban worker workflow patterns for all project boards — label-based PRs, respawn guard, selective profile skill management, worker tuning, PR consolidation, native vs custom infrastructure audit."
version: 1.3.0
metadata:
  hermes:
    tags: [kanban, workflow, pr, ci, shared]
---

# Kanban Project Workflow — Shared Patterns

Universal kanban worker patterns for project boards (shop, the-swarm, music-library, etc.).
Load this skill alongside the project-specific skill for every coder/reviewer task.

## GitHub Models

Two repo models are used across projects. Your project skill will tell you which one.

### Fork Model (shop, music-library)

Push to `Seven74AI/<repo>` fork. PRs go to upstream (`mnlamart/<repo>`).
Only consolidation merges go to upstream. Workers NEVER push directly to upstream.

```
Worker branch → Seven74AI/<repo> fork → PR to mnlamart/<repo> upstream
```

### Direct Model (the-swarm, videogame-lab)

Push directly to `Seven74AI/<repo>`. No upstream fork. Code lives in one repo.

```
Worker branch → Seven74AI/<repo> (direct push, no fork)
```

## ⛔ CRITICAL: Label-Based PR Workflow — NO PR URLs in Comments

The kanban dispatcher scans task comments for GitHub PR URLs. If ANY comment
within the last 24 hours matches `https://github.com/.../pull/N`, the task is
flagged `respawn_guarded` with reason `active_pr`. The worker cannot respawn
for 24 hours.

## Unified PR Workflow (ALL project boards)

**Single workflow for every board — shop, the-swarm, music-library, etc.**
One flow: CI gates correctness, reviewer agent gates quality, GitHub native
auto-merge handles the rest. No per-project variation.

```
Coder → PR + auto-merge → block (review-required) → Reviewer agent approves
       → CI green → GitHub auto-merge → Light watchdog unblocks → Coder complete
```

### Coder (step-by-step)

```python
# 1. Clone repo, implement, run CI in background
terminal("vitest run && tsc --noEmit && lint", background=true, notify_on_complete=true)

# 2. Push branch, create PR with kanban label
terminal(f"gh pr create --repo {REPO} --base main --head feat/X "
         f"--label 'kanban:{os.environ[\"HERMES_KANBAN_TASK\"]}' "
         f"--title '...' --body '...'")

# 3. Enable GitHub native auto-merge (merges when CI green + approved)
terminal(f"gh pr merge --auto --squash")

# 4. Create reviewer task (standalone — NEVER with parent=)
kanban_create(
    title=f"Review: (t_{os.environ['HERMES_KANBAN_TASK']}) <summary>",
    assignee="reviewer",
    skills=["github-code-review", "kanban-project-workflow"],
    body="Review the work from the coder task.",
)

# 5. Block yourself
kanban_block(reason="review-required: PR label kanban:$HERMES_KANBAN_TASK")
```

GitHub auto-merge (`--auto`) handles the CI gate natively — no custom watchdog
needed for merging. When all required status checks pass AND the reviewer
approves, GitHub merges automatically.

### Reviewer agent (step-by-step)

```python
# 1. Read coder's handoff from their task comment thread
kanban_show()

# 2. Review the PR (pull diff, read code, run tests)
terminal(f"gh pr diff {PR_NUMBER} --repo {REPO}")

# 3a. Approve — unblocks auto-merge
terminal(f"gh pr review {PR_NUMBER} --repo {REPO} --approve")
kanban_complete(
    summary="Reviewed PR #N; approved — code correct, tests pass",
    metadata={"approved": True}
)

# 3b. Request changes — auto-merge blocked
terminal(f"gh pr review {PR_NUMBER} --repo {REPO} --request-changes -b '...'")
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
Always check the workflow file after consolidation PRs — `|| true` is a
magnet for copy-paste regressions.

## Pitfall: Stale Fork Base — Unmerged Commits on Feature Branches

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

## ⛔ CRITICAL: Label-Based PR Workflow — NO PR URLs in Comments

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

## Pitfall: Manual GitHub Merge ≠ Kanban Completion

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
2. Every profile gets the project skills for its boards
3. Beyond that, each role gets ONLY what it uses:

| Role | Extra skills |
|------|-------------|
| `coder` | `tdd`, `systematic-debugging`, `github-pr-workflow`, `requesting-code-review`, `project-ci`, `long-running-tests`, `disk-cleanup`, `codebase-inspection`, `subagent-driven-development`, `writing-plans` |
| `reviewer` | `github-code-review`, `systematic-debugging`, `codebase-inspection`, `project-ci`, `requesting-code-review` |
| `researcher` | `arxiv`, `blogwatcher`, `llm-wiki` (if needed) |
| `planner` | `writing-plans`, `plan`, `spike`, `subagent-driven-development` |
| `hermes-devops` | `kanban-ci-watchdog`, `kanban-velocity`, `kanban-profile-blueprint`, `hermes-journal`, `disk-cleanup`, `webhook-subscriptions`, all `github-*`, `renovate-bulk-merge`, `hermes-agent`, `project-ci`, `long-running-tests` |

External skill suites (Matt Pocock, etc.) are added only to roles that benefit:
`coder` might get `tdd`, `diagnose`, `triage`; `reviewer` might get `diagnose`;
`researcher` and `planner` typically don't need them.

**To sync a skill to specific profiles (NOT all):**

```bash
for p in coder planner; do
  mkdir -p "/root/.hermes/profiles/$p/skills/<category>/<skill-name>"
  cp /root/.hermes/skills/<category>/<skill-name>/SKILL.md \
     "/root/.hermes/profiles/$p/skills/<category>/<skill-name>/SKILL.md"
done
```

Missing profile copies cause "Unknown skill(s): <name>" crashes on worker spawn.
If a task's `--skills` references a skill not in the worker's profile, the spawn
fails.

## Worker Tuning

### `max_iterations` — set to 120

Default 50 causes "Iteration budget exhausted" on complex tasks (e2e test runs,
migrations, multi-file refactors). All worker profiles should have:

```yaml
kanban:
  max_iterations: 120
```

Set via: `hermes config set --profile <name> kanban.max_iterations 120`

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

## PR Consolidation

When multiple open PRs overlap (e.g., dep bumps + CI fixes + migration),
consolidate into one PR:

1. Check which PRs are already merged on main (`gh pr view` + `git log`)
2. Apply remaining changes onto a single branch off main
3. Run full local CI in background + wait
4. Push to fork, create a single consolidated PR
5. Close superseded PRs with comment

## Pitfall: Reviewer Agent Needs a Separate GitHub Account

The coder worker runs under the `coder` profile which uses the `Seven74AI`
GitHub token. The reviewer worker ALSO uses `Seven74AI`'s token. GitHub's
branch protection does NOT count a PR author's own approving review toward
the required approval count — so `gh pr review --approve` from `Seven74AI`
on a PR opened by `Seven74AI` will not unblock auto-merge.

**Symptom:** PR has CI green + reviewer approved, but auto-merge never triggers.
`gh pr view --json autoMergeRequest` shows `mergeStateStatus: BLOCKED`.

**Fix:** Create a separate GitHub machine account (e.g., `hermes-reviewer`) with
write access to the target repos. Configure the `reviewer` Hermes profile to use
that token. The reviewer's approve will then count as a distinct user.

```bash
# In reviewer profile's .env:
GITHUB_TOKEN=ghp_reviewer_token_here
```

**Alternative:** Disable required approvals in branch protection and rely on CI
only for auto-merge. The reviewer still comments but doesn't gate the merge.
Less safe — code lands without explicit approval.

## Standard Pipeline

All project boards follow the same role pipeline:

```
Researcher → Planner → Coder → Reviewer → Done
```

- **Researcher:** Investigate, compare approaches, produce recommendations.
  Handoff: `kanban_complete(summary=..., metadata={recommendation, benchmarks})`
- **Planner:** Break work into concrete implementation steps. May `kanban_create`
  subtasks for the coder. Handoff: wireframe, task list, or child tasks.
- **Coder:** Implement, test, open PR, enable auto-merge, create reviewer task,
  block. Handoff: PR auto-merge enabled, reviewer task created.
- **Reviewer:** Pull PR diff, review code, approve or request changes. Approve
  unblocks auto-merge; request-changes requires coder fix + re-review.

All boards use the same unified PR workflow (CI + reviewer → auto-merge).
No per-board variation. Project-specific details (GitHub model, tech stack,
testing conventions) live in the project skill (`shop`, `the-swarm`, etc.).

## Health Checks

### Pre-Spawn Watchdog (automated)

A notification-only cron (`pre-spawn-watchdog.py`, every 5 min) scans all boards
for ready tasks with issues. It reports to Discord but takes NO action:

- `NO-SKILLS` — skills is NULL or empty
- `NO-MRT` — max_runtime_seconds is NULL
- `PR-URL-IN-BODY` — task body contains a github.com PR URL
- `PR-URL-COMMENTS(N)` — N comments contain github.com PR URLs  
- `NO-ASSIGNEE` — no assignee (expected for RECETTE bookmarks)

Silent when clean. Created 2026-05-20 (cron `ceead0ca5089`).

### One-Shot Cleanup (manual, after major updates)

After creating/updating shared skills or changing profile configs, run a one-shot
cleanup to fix stale tasks that were created before the updates. See
`references/cleanup-ready-tasks.md` for the full script.

Fixes: NULL skills → set to board-appropriate skills list, NULL mrt → 3600,
PR URLs in bodies → replaced with text references.
