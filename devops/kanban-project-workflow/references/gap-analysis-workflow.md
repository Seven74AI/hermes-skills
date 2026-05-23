# Gap Analysis Workflow — Kanban "Done" vs Upstream Reality

When a large consolidation PR merges many feature branches to upstream, the kanban board may show tasks as "done" that never actually landed. This workflow detects the gaps.

## When to Trigger

- After a consolidation PR merges (fork → upstream) with 50+ commits
- After any bulk squash-merge that could have omitted branches
- When a spot-check reveals features missing from upstream despite "done" kanban tasks
- After any merge that touched 10+ feature branches

## Step 1: Researcher — Full Gap Audit

Task body template:

```
## Mission

Compare every "done" implementation task on the <board> kanban board against the actual code in upstream <repo> (HEAD: <sha>, consolidation PR #N).

## Method

1. Query kanban DB for all "done" implementation tasks:
   SELECT id, title, body FROM tasks WHERE status='done'
   AND id NOT IN (SELECT child_id FROM task_links) -- skip parent-only (meta)
   ORDER BY id

2. For each task, check if the feature exists in upstream:
   - Prisma models: grep "^model " prisma/schema.prisma
   - Utility files: find app/utils -name '*<keyword>*'
   - Route files: find app/routes -name '*<keyword>*'
   - Components: find app/components -name '*<keyword>*'

3. Categorize each task as LANDED / MISSING / PARTIAL / META

4. For MISSING features, note expected artifacts and priority
```

## Step 2: Researcher Deliverable

Output format (save to /tmp/<board>-gap-analysis.md):

```
## Executive Summary
- X total done tasks → Y implementation candidates → A LANDED / B MISSING / C PARTIAL
- Gap rate: B/Y = Z%

## MISSING Features by Priority
### HIGH (N tasks)
| Task ID | Feature | Expected Artifacts |

### MEDIUM (N tasks)
...

## Root Cause
Pattern analysis — e.g. "new Prisma models were omitted from consolidation"

## Board Cleanup
- Tasks to REOPEN (N)
- Tasks to REVIEW (N — PARTIAL)
```

## Step 3: Planner — Create Implementation Tickets

The planner reads the gap report and creates coder tasks:

1. **HIGH gaps first** — create one coder task per gap
2. **Respect Prisma dependencies** — AuditLog model BEFORE audit log UI, Coupon model BEFORE checkout integration
3. Each ticket gets:
   - `--skill` list appropriate for coder (tdd, systematic-debugging, kanban-project-workflow, etc.)
   - `--max-runtime 3600`
   - Body referencing the original feature spec and expected artifacts
4. Do NOT create tickets for LANDED or META tasks

## Step 4: Coder — Re-Implement

Standard coder workflow: implement → PR → auto-merge → reviewer task → block.

Key difference from normal coder tasks: the coder starts from **upstream main**, not the fork. The fork had the feature once but it was lost in consolidation; re-implementing from scratch on a clean base avoids stale fork contamination.

## Why Gaps Happen

Consolidation PRs that squash-merge 200+ commits can omit branches that:
- Added new Prisma models with migrations
- Had merge conflicts that were resolved by dropping the feature
- Were on feature branches that were never merged into the consolidation branch

The kanban board tracks worker activity (fork work), not upstream reality. After a consolidation, the two diverge.
