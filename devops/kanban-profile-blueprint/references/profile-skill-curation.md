# Profile Skill Curation

Each kanban worker profile has its own copy of `skills/` at `~/.hermes/profiles/<name>/skills/`.
The default profile has 118 skills (was 128 — removed apple×5, gaming×2, smart-home, edgee-lab, test-driven-development duplicate).

**Philosophy: reduce to what each role actually needs.** Every skill in the `available_skills` block costs ~25-35 tokens per turn in the system prompt. 108 skills → ~3000 tokens wasted. 24 skills → ~670 tokens.

## Current Profile Layouts (2026-05-21)

### Coder (24 skills)
```
kanban-worker, kanban-project-workflow
shop, the-swarm, music-library, baguette, glance, videogame-lab
tdd, diagnose, triage, prototype, grill-with-docs, improve-codebase-architecture
systematic-debugging, long-running-tests, project-ci, requesting-code-review
writing-plans, subagent-driven-development, codebase-inspection
github-pr-workflow, github-auth, disk-cleanup
```

### Reviewer (14 skills)
```
kanban-worker, kanban-project-workflow
shop, the-swarm, music-library
diagnose, systematic-debugging, project-ci, requesting-code-review, codebase-inspection
github-code-review, github-pr-workflow, github-auth, disk-cleanup
```

### Researcher (12 skills)
```
kanban-worker, kanban-project-workflow
shop, the-swarm, music-library, baguette, glance
arxiv, blogwatcher, llm-wiki
grill-me, diagnose
```

### Planner (8 skills)
```
kanban-orchestrator, kanban-project-workflow
shop, the-swarm, music-library, baguette, glance, videogame-lab
```
Project skills loaded on-demand via `HERMES_TENANT` (see SOUL.md template).

### Hermes-devops (19 skills)
```
kanban-worker, kanban-project-workflow
hermes-agent, hermes-journal, disk-cleanup, webhook-subscriptions
kanban-ci-watchdog, kanban-velocity, kanban-profile-blueprint
project-ci, long-running-tests
github-auth, github-pr-workflow, github-code-review, github-issues,
github-repo-management, codebase-inspection, renovate-bulk-merge
diagnose
```

### Inactive (untouched)
- `edgee-planner`: 106 skills
- `twitter-coder`: 106 skills

## Sync Procedure

After any skill update, sync only to the profiles that need it:

```bash
# Example: sync a skill to coder and reviewer
for p in coder reviewer; do
  mkdir -p "/root/.hermes/profiles/$p/skills/<category>/<skill>"
  cp /root/.hermes/skills/<category>/<skill>/SKILL.md \
     "/root/.hermes/profiles/$p/skills/<category>/<skill>/SKILL.md"
done
```

**NEVER sync to ALL profiles.** The `edgee-planner` and `twitter-coder` profiles are inactive — updating them is wasted effort. Only sync to active profiles: `coder`, `reviewer`, `researcher`, `planner`, `hermes-devops`.

## Pitfall: Missing Skill → "Unknown skill(s)" Crash

If a task's `--skills` references a skill not in the worker's profile, the spawn fails with "Unknown skill(s): <name>". The dispatcher auto-blocks after `failure_limit` consecutive failures. Fix: sync the missing skill to the profile, then `--reclaim` + `dispatch`.

## Pitfall: Task Skills Code

Tasks created via `hermes kanban create --skill X` store skills as JSON arrays in the `skills` column. When you update profile skills, existing tasks still reference their old skill lists. The coder `kanban_create()` from the new workflow automatically includes role-appropriate skills, so new tasks are fine. Old tasks need manual update if their skills list is stale.
