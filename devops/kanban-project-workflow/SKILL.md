---
name: kanban-project-workflow
description: "Shared kanban worker workflow patterns for all project boards — label-based PRs, respawn guard, selective profile skill management, worker tuning, PR consolidation, native vs custom infrastructure audit."
version: 1.4.0
metadata:
  hermes:
    tags: [kanban, workflow, pr, ci, shared]
---

# Kanban Project Workflow — Shared Patterns

Universal kanban worker patterns for all project boards (shop, the-swarm, music-library, etc.).
Load this skill alongside the project-specific skill for every coder/reviewer task.

## Unified Workflow

ALL projects use the same flow — review-gated with auto-merge:

```
Coder → PR + auto-merge → block "review-required" → Reviewer approves → CI green → GitHub merges auto → CI watchdog unblocks → Coder completes
```

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
2. **Exception:** `planner` gets `kanban-orchestrator` instead of `kanban-worker` — it never implements code
3. Every profile gets the project skills for its boards (planner loads them on demand via `skill_view()` based on `HERMES_TENANT`)
4. Beyond that, each role gets ONLY what it uses:

| Role | Extra skills |
|------|-------------|
| `coder` | `tdd`, `systematic-debugging`, `github-pr-workflow`, `requesting-code-review`, `project-ci`, `long-running-tests`, `disk-cleanup`, `codebase-inspection`, `subagent-driven-development`, `writing-plans` |
| `reviewer` | `github-code-review`, `systematic-debugging`, `codebase-inspection`, `project-ci`, `requesting-code-review` |
| `researcher` | `arxiv`, `blogwatcher`, `llm-wiki` (if needed) |
| `planner` | `kanban-orchestrator`. Core: `kanban-project-workflow` only (NOT `kanban-worker`). Project skills (shop, the-swarm, etc.) loaded on-demand via `HERMES_TENANT` → `skill_view()`. Personality: `technical`. |
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

## Pitfall: Reviewer App Approval Not Counting (`authorAssociation: NONE`)

Even with `Contents: Read & Write` on the GitHub App, reviews can show
`authorAssociation: "NONE"` and NOT count toward branch protection.
**Symptom:** `mergeStateStatus: "BLOCKED"` with 1 APPROVED review, all CI green.

**Immediate fix:** Admin-merge the PR:
```bash
gh pr merge N --repo <repo> --admin --squash --delete-branch
```

**Diagnosis:**
```bash
gh pr view N --repo <repo> --json reviews --jq '[.reviews[] | {state, authorAssociation}]'
# authorAssociation: "NONE" → review doesn't count
```

Real case: music-library#4 (2026-05-21) — hermes-sevenai-reviewer approved, all CI green,
but `authorAssociation: NONE` blocked auto-merge. Admin-merge was the workaround.

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

## Status Checks: PRs + Kanban Multi-Board

Quick audit across all project boards — forks, upstream repos, and kanban tickets.
See `references/cross-repo-pr-status.md` for the one-liner pattern.

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
