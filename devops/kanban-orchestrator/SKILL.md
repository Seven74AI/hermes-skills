---
name: kanban-orchestrator
description: Decomposition playbook + anti-temptation rules for an orchestrator profile routing work through Kanban. The "don't do the work yourself" rule and the basic lifecycle are auto-injected into every kanban worker's system prompt; this skill is the deeper playbook when you're specifically playing the orchestrator role.
version: 4.3.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [kanban, multi-agent, orchestration, routing]
    related_skills: [kanban-worker]
---

# Kanban Orchestrator — Decomposition Playbook

> The **core worker lifecycle** (including the `kanban_create` fan-out pattern and the "decompose, don't execute" rule) is auto-injected into every kanban process via the `KANBAN_GUIDANCE` system-prompt block. This skill is the deeper playbook when you're an orchestrator profile whose whole job is routing.

## Team bootstrap (creating a new profile roster)

When a user wants to spin up a new autonomous team (e.g., "videogame-lab", "startup-lab"), see `references/team-bootstrap.md` for the full recipe: naming conventions, clone-from-default pattern, and pitfalls.

## Profiles are user-configured — not a fixed roster

Hermes setups vary widely. Some users run a single profile that does everything; some run a small fleet (`docker-worker`, `cron-worker`); some run a curated specialist team they've named themselves. There is **no default specialist roster** — the orchestrator skill does not know what profiles exist on this machine.

Before fanning out, you must ground the decomposition in the profiles that actually exist. The dispatcher silently fails to spawn unknown assignee names — it doesn't autocorrect, doesn't suggest, doesn't fall back. So a card assigned to `researcher` on a setup that only has `docker-worker` just sits in `ready` forever.

**Step 0: discover available profiles before planning.**

Use one of these:

- `hermes profile list` — prints the table of profiles configured on this machine. Run it through your terminal tool if you have one; otherwise ask the user.
- `kanban_list(assignee="<some-name>")` — sanity-check a single name. Returns an empty list (rather than an error) for an unknown assignee, so this only confirms a name you're already considering.
- **Just ask the user.** "What profiles do you have set up?" is a fine first turn when the goal needs more than one specialist.

Cache the result in your working memory for the rest of the conversation. Re-asking every turn wastes a tool call.

## When to use the board (vs. just doing the work)

Create Kanban tasks when any of these are true:

1. **Multiple specialists are needed.** Research + analysis + writing is three profiles.
2. **The work should survive a crash or restart.** Long-running, recurring, or important.
3. **The user might want to interject.** Human-in-the-loop at any step.
4. **Multiple subtasks can run in parallel.** Fan-out for speed.
5. **Review / iteration is expected.** A reviewer profile loops on drafter output.
6. **The audit trail matters.** Board rows persist in SQLite forever.

If *none* of those apply — it's a small one-shot reasoning task — use `delegate_task` instead or answer the user directly.

## The anti-temptation rules

Your job description says "route, don't execute." The rules that enforce that:

- **Do not execute the work yourself.** Your restricted toolset usually doesn't even include terminal/file/code/web for implementation. If you find yourself "just fixing this quickly" — stop and create a task for the right specialist.
- **For any concrete task, create a Kanban task and assign it.** Every single time.
- **Split multi-lane requests before creating cards.** A user prompt can contain several independent workstreams. Extract those lanes first, then create one card per lane instead of bundling unrelated work into a single implementer card.
- Run independent lanes in parallel. If two cards do not need each other's output, leave them unlinked so the dispatcher can fan them out. Link only true data dependencies.
- **Never create dependent work as independent ready cards.** If a card must wait for another card, pass `parents=[...]` in the original `kanban_create` call. Do not create it first and link it later, and do not rely on prose like "wait for T1" inside the body.
- **After decomposition, audit the new tickets.** Check max_runtime (must be 3600s), body (must not be NULL), and parent/child links. See `kanban-profile-blueprint` skill → `references/ticket-audit-pattern.md` for the SQL query.
- **If no specialist fits the available profiles, create a new one.** Use `hermes profile create <name> --clone-from <base>` to add a profile for a new role. Never create clones (no -2, -3) — one profile per role max.
- **Decompose, route, and summarize — that's the whole job.**

## Decomposition playbook

### Step 1 — Understand the goal

Ask clarifying questions if the goal is ambiguous. Cheap to ask; expensive to spawn the wrong fleet.

### Step 2 — Sketch the task graph

Before creating anything, draft the graph out loud (in your response to the user). Treat every concrete workstream as a candidate card:

1. Extract the lanes from the request.
2. Map each lane to one of the profiles you discovered in Step 0. If a lane doesn't fit any existing profile, ask the user which to use or create.
3. Decide whether each lane is independent or gated by another lane.
4. Create independent lanes as parallel cards with no parent links.
5. Create synthesis/review/integration cards with parent links to the lanes they depend on. A child created with unfinished parents starts in `todo`; the dispatcher promotes it to `ready` only after every parent is done.

Examples of prompts that should fan out (using placeholder profile names — substitute whatever exists on the user's setup):

- "Build an app" → one card to a design-oriented profile for product/UI direction, one or two cards to engineering profiles for implementation, plus a later integration/review card if the user has a reviewer profile.
- "Fix blockers and check model variants" → one implementation card for the blocker fixes plus one discovery/research card for config/source verification. A final reviewer card can depend on both.
- "Research docs and implement" → a docs-research card can run in parallel with a codebase-discovery card; implementation waits only if it truly needs those findings.
- "Analyze this screenshot and find the related code" → one card to a vision-capable profile for the visual analysis while another searches the codebase.

Words like "also," "finally," or "and" do not automatically imply a dependency. They often mean "make sure this is covered before reporting back." Only link tasks when one card cannot start until another card's output exists.

Show the graph to the user before creating cards. Let them correct it — including which actual profile name should own each lane.

### Step 2.5 — Scale profiles to match parallelism

Once the task graph is approved, compute how many profiles of each type are needed to run all parallel lanes simultaneously. **Create or remove profiles to match.**

**Rule:** For each profile role (coder, researcher, reviewer, etc.), **hard cap: 1 profile per role, globally.** No clones. The dispatcher already spawns multiple workers per profile (observed: 7× music-reviewer workers from 1 profile), so adding clone profiles would multiply the overspawning problem. On 8GB hosts, the gateway alone uses ~3-5GB and each worker adds ~120MB — with cap=1 and the dispatcher overspawning, 20+ workers can already push memory to 6-7GB. Cloning would guarantee OOM.

```bash
# NO CLONING. Each role gets exactly ONE profile.
# If a project needs a coder: use the shared `coder` profile.
# Do NOT create -2, -3 clones. Delete any existing clones.
hermes profile delete <name>-2 --yes
```

**Naming convention:** generic profiles shared across all boards: `coder`, `researcher`, `reviewer`, `planner`. One profile per role max, no clones, no project prefix.

**When to scale up:** NEVER. Cap is always 1. No clones.

**When NOT to scale up:** Always. All tasks queue on the single profile.

**Anti-patterns:**
- NEVER clone a profile — 1 per role is the hard cap
- Delete ALL `-2` and `-3` clones immediately if they exist
Keep the base profile — it's the only one for that role.

### Step 2.6 — Autonomous profile scaling (DISABLED)

Profile cloning is disabled (cap=1, no clones). The autoscale cron is NOT needed and should be removed if it exists:

```bash
hermes cron remove <kanban-autoscale-job-id>
```

### Step 3 — Create tasks and link

Use the profile names from Step 0. The example below uses placeholders `<profile-A>`, `<profile-B>`, `<profile-C>` — replace them with what the user actually has.

```python
t1 = kanban_create(
    title="research: Postgres cost vs current",
    assignee="<profile-A>",  # whichever profile handles research on this setup
    body="Compare estimated infrastructure costs, migration costs, and ongoing ops costs over a 3-year window. Sources: AWS/GCP pricing, team time estimates, current Postgres bills from peers.",
    tenant=os.environ.get("HERMES_TENANT"),
)["task_id"]

t2 = kanban_create(
    title="research: Postgres performance vs current",
    assignee="<profile-A>",  # same profile, run in parallel
    body="Compare query latency, throughput, and scaling characteristics at our expected data volume (~500GB, 10k QPS peak). Sources: benchmark papers, public case studies, pgbench results if easy.",
)["task_id"]

t3 = kanban_create(
    title="synthesize migration recommendation",
    assignee="<profile-B>",  # whichever profile does synthesis/analysis
    body="Read the findings from T1 (cost) and T2 (performance). Produce a 1-page recommendation with explicit trade-offs and a go/no-go call.",
    parents=[t1, t2],
)["task_id"]

t4 = kanban_create(
    title="draft decision memo",
    assignee="<profile-C>",  # whichever profile drafts user-facing prose
    body="Turn the analyst's recommendation into a 2-page memo for the CTO. Match the tone of previous decision memos in the team's knowledge base.",
    parents=[t3],
)["task_id"]
```

`parents=[...]` gates promotion — children stay in `todo` until every parent reaches `done`, then auto-promote to `ready`. No manual coordination needed; the dispatcher and dependency engine handle it.

If the task graph has dependencies, create the parent cards first, capture their returned ids, and include those ids in the child card's `parents` list during the child `kanban_create` call. Avoid creating all cards in parallel and linking them afterward; that creates a window where the dispatcher can claim a child before its inputs exist.

### Step 4 — Complete your own task

If you were spawned as a task yourself (e.g. a planner profile was assigned `T0: "investigate Postgres migration"`), mark it done with a summary of what you created:

```python
kanban_complete(
    summary="decomposed into T1-T4: 2 research lanes in parallel, 1 synthesis on their outputs, 1 prose draft on the recommendation",
    metadata={
        "task_graph": {
            "T1": {"assignee": "<profile-A>", "parents": []},
            "T2": {"assignee": "<profile-A>", "parents": []},
            "T3": {"assignee": "<profile-B>", "parents": ["T1", "T2"]},
            "T4": {"assignee": "<profile-C>", "parents": ["T3"]},
        },
    },
)
```

### Step 5 — Report back to the user

Tell them what you created in plain prose, naming the actual profiles you used:

> I've queued 4 tasks:
> - **T1** (`<profile-A>`): cost comparison
> - **T2** (`<profile-A>`): performance comparison, in parallel with T1
> - **T3** (`<profile-B>`): synthesizes T1 + T2 into a recommendation
> - **T4** (`<profile-C>`): turns T3 into a CTO memo
>
> The dispatcher will pick up T1 and T2 now. T3 starts when both finish. You'll get a gateway ping when T4 completes. Use the dashboard or `hermes kanban tail <id>` to follow along.

## Team Bootstrap

Full workflow for creating a new Kanban team from scratch: profiles, SOUL.md, GitHub, Notion, Kanban board, and launching the first ideation pipeline. See `references/team-bootstrap.md`.

## Common patterns

**Fan-out + fan-in (research → synthesize):** N research-style cards with no parents, one synthesis card with all of them as parents.

**Parallel implementation + validation:** one implementer card makes the change while one explorer/researcher card verifies config, docs, or source mapping. A reviewer card can depend on both. Do not make the implementer own unrelated verification just because the user mentioned both in one sentence.

**Pipeline with gates:** `planner → implementer → reviewer`. Each stage's `parents=[previous_task]`. Reviewer blocks or completes; if reviewer blocks, the operator unblocks with feedback and respawns.

**Same-profile queue:** N tasks, all assigned to the same profile, no dependencies between them. The dispatcher may claim multiple tasks for the same profile simultaneously (observed: 3× coder workers at once). Do not assume serialization — on memory-constrained hosts, unblock tasks in small batches (5-10 at a time) to avoid spawning too many workers and triggering OOM.

**Review-required trap for automated pipelines.** Workers that call `kanban_block(reason="review-required")` block the task permanently until a human unblocks it — no reviewer profile is automatically assigned. For autonomous teams with reviewer profiles, teach workers the **block + create standalone** pattern:

1. Code and test the change
2. `kanban_block(reason="review-required: <summary>")` — blocks the coder, keeping it alive for fixes
3. `kanban_create()` a NEW review task assigned to the reviewer profile **WITHOUT `parent=`** — standalone, references the coder task ID in body text
4. The reviewer picks up the review task, approves/rejects/needs-changes
5. If approved → reviewer unblocks the coder, coder re-runs and completes
6. If needs changes → reviewer blocks self, creates fix task for coder

**⛔ NEVER use `parent=` on reviewer tasks.** The dispatcher does not promote `todo` children of blocked parents — creating a reviewer with `parent=coder_task_id` locks it in `todo` forever (deadlock observed on music-library board 2026-05-18: 6 reviewer tasks stuck until archived and recreated without parents). Always create reviewers standalone and include the coder task ID in the body text instead.

**Pre-check for duplicates:** Before creating a review task, scan the board for an existing review with a similar title. If found, link to it instead of creating a duplicate.

**Human-in-the-loop:** Any task can `kanban_block()` to wait for input. Dispatcher respawns after `/unblock`. The comment thread carries the full context. For automated review, use the complete+create pattern above instead of review-required.

**Phased dependency update pipeline:** For large npm dep updates (20+ packages, major jumps), decompose into a 6-task chain: research (parallel) → minors → likely-safe majors → risky majors → known-breaking → verification. Full task graph, phase details, package categorization, and advanced split-and-merge pattern in `references/dependency-update-pipeline.md`.

**Parallelism with cap=1:** Since each role has exactly one profile, all tasks assigned to that role are serialized — the dispatcher queues them (though it may overspawn workers). No cloning.

**Split-and-merge for complex monolithic tasks:** When a single task does too many unrelated fixes that COULD run in parallel, split it. Full step-by-step pattern: `references/task-splitting.md`. Covers when to split, chain-vs-parallel decision, dependency preservation (parents→sub1, children→subN), and verification.

**Bundle decomposition (multi-feature → parallel atomics):** When a ticket bundles 2+ independent features (visible from combined tags like `[GM-2+GM-3+GM-10]`), decompose into parallel atomic tasks. Different from chain-splitting — these are genuinely independent features that can run concurrently. Full recipe: `references/bundle-decomposition.md`.

**Block Watchdog:** For automated detection and recovery of abnormally blocked tasks (crashes, OOM, iteration budget, missing reviewer tasks). Full pattern in `references/block-watchdog.md`.:

- **T-base** → apply all changes, commit to a shared branch (no fixes yet)
- **T-fix-A ∥ T-fix-B ∥ T-fix-C** → parallel workers, each handling a different concern (e.g., config files vs. code types vs. UI classes), assigned to DIFFERENT profiles so the dispatcher runs them concurrently
- **T-merge** → depends on all fix tasks, merges their branches, runs the full test suite

Constraints:
- Each fixer must work on non-overlapping file areas to avoid git conflicts. If two fixers must touch the same file, serialize them or use git worktrees.
- Archive the original monolithic task before creating the split replacement.
- Update downstream parent links (`hermes kanban link/unlink`) so tasks after the merge point depend on T-merge, not the archived original.
- Full example in `references/dependency-update-pipeline.md`.
- **No cloning — cap is 1 per role. All tasks queue on the single profile.**
- **Category-competitor trap in research scoping.** When creating research tasks about a company's competitive landscape, don't search for competitors in the company's broad product *category* (e.g. "AI gateways"). Search in the company's core *differentiator* (e.g. "token compression"). A company that makes an AI gateway with unique compression tech competes with other compression solutions, not with general-purpose gateways. Scoping by category produces a comparison set that misses the real threats and overstates the company's uniqueness. **Real case (edgee-lab 2026-05-18):** T3 analyzed 8 AI gateways and concluded Edgee was "the only one with token compression" — a tautology, since none of the selected competitors even attempt compression. The correct comparison set would be token compression tools, context window optimizers, and prompt caching services.
2. After the final review task completes, verify all tasks are resolved:
   ```bash
   hermes kanban --board <board> list
   ```
Keep the base profile — it's the only one for that role.

**Ideation pipeline (multi-agent brainstorming):** For open-ended project ideation ("generate N ideas for a service that helps people"), decompose into planner → N parallel researchers → reviewer. Each researcher explores different domains, reviewer selects and polishes the top ideas. Full task graph, body templates, and scaling rules in `references/ideation-pipeline.md`.

**Postpone a blocked task to the end of a chain:** When the head of a sequential chain is blocked on an external resource (expired cookies, missing credential) but downstream tasks can run independently, reorder the chain: unblock → unlink old parent → link last child as new parent. The blocked task moves to the end; everything else proceeds. Full recipe and multi-parent awareness in `references/postpone-blocked-task.md`.

**Board migration (moving tasks between boards):** When a tenant's tasks are on the wrong board (e.g. `music-library` tasks on `default`), use the recreate+archive pattern: reclaim/unblock → recreate on target board → archive on source. Step-by-step recipe, CLI pitfalls (`--board` position, board switch unreliability, shell quoting), and parent/child link handling in `references/board-migration.md`.

**Team creation from scratch:** When the user wants a new specialist AI agent team (profiles, Kanban board, GitHub repo, Notion page, cron jobs), follow the full 7-step recipe in `references/team-creation-checklist.md`. Covers: roster design, profile creation, SOUL.md authoring, infrastructure setup, task decomposition, recurring jobs, and verification.

**Phased dependency update pipeline:** For large npm dep updates (20+ packages, major jumps), decompose into a 6-task chain: research (parallel) → minors → likely-safe majors → risky majors → known-breaking → verification. Full task graph, phase details, package categorization, and advanced split-and-merge pattern in `references/dependency-update-pipeline.md`.

## Pitfalls

**Reaching for external tools before checking internal Kanban.** If a user asks to set up a team, project, or multi-agent workflow, the Hermes Kanban system (profiles + dispatcher) is the first tool to consider — not Linear, Jira, Notion, or any external SaaS. Load this skill before suggesting external tools.

**GitHub issues are NOT kanban tickets — ops workers never see them.** The hermes-ops team (`hermes-devops`, `hermes-researcher`, etc.) processes tasks exclusively through the `hermes-ops` kanban board. When a user says "create a ticket for the ops team," the task MUST be created as a kanban ticket (`hermes kanban --board hermes-ops create ...`). A GitHub issue alone — even on `Seven74AI/hermes-agent` — will sit with zero comments indefinitely because ops workers don't monitor GitHub issues. GitHub issues are for external-facing requests and code-related tracking; kanban is the ops team's work queue. **Real case (2026-06-08):** MCP Knowledge Base issue (#2) created on GitHub, never dispatched to kanban → 24h later, 0 comments, task untouched. Fix: also create the kanban ticket on `hermes-ops` with `--assignee researcher`.

**Inventing profile names that don't exist.** The dispatcher silently fails to spawn unknown assignees — the card just sits in `ready` forever. Always assign to a profile from your Step 0 discovery; ask the user if you're unsure.

**Unassigned tasks (no assignee at all).** Tasks created without an `--assignee` sit in `ready` forever — the dispatcher only claims tasks that have a valid assignee. This is different from wrong-assignee (above): here the task was never assigned to anyone. When you see `(unassigned)` on a board, the tasks will never run. Fix: batch-reassign them to a valid profile.

```bash
# Batch-reassign all unassigned ready tasks to a profile
hermes kanban --board <board> list 2>&1 | grep 'unassigned' | awk '{print $2}' | while read id; do
  hermes kanban --board <board> reassign "$id" <profile> --reclaim
done
```

**Real case (2026-05-19):** hermes-skills board had 19 `ready` tasks all `(unassigned)` — zero progress until batch-reassigned to `coder`. After reassignment, the dispatcher picked them up within seconds.

**Never guess task body content when the user is about to supply it.** If the user says "add a task for X" and X involves a URL, file, or data the user hasn't provided yet, do NOT fill the task body with assumed content from context. Wait for the user to give you the actual source. Creating a task with guessed content wastes a task slot (the dispatcher picks it up immediately) and forces an archive+recreate cycle. **Real case (2026-05-25):** user said "on va lancer un ticket pour ajouter un reel" — agent created a task for the Rich Sol Foods reel from earlier KB context instead of waiting for the URL the user was about to send. Task archived 30s later and recreated with the correct URL.

**Never create tickets from unverified audit claims.** When decomposing an audit (drift audit, code review, spec-vs-implementation gap analysis) into kanban tickets, verify EVERY claim against the actual source code before creating the ticket. Each ticket must cite a specific file:line. Audits that make claims like "X is missing," "Y uses Z instead of W," or "boundary detection uses regex instead of LLM" must be confirmed by reading the relevant source files first. Creating tickets from unverified claims floods the board with false positives — reviewers and coders waste time on problems that don't exist, and real bugs get buried. **Real case (kb-agent 2026-06-19):** 10 drift tickets created → 5 false, 1 debatable, 1 partial. Review tickets were spawned for fake problems, consuming worker cycles and OOM risk.

**Never say "cause probable" — user demands definitive root cause.** When investigating failures (corruption, crashes, missing data), do not present speculative conclusions. Either prove the cause with evidence (logs, file timestamps, integrity checks, code traces) or state what remains unknown. "Probable" is not acceptable. **Real case (2026-05-27):** agent said "Cause probable : une notification malformée" — user rejected this and demanded "une cause sûre." Full investigation revealed the real cause (WAL corruption from a 2-day-old crash). The notification error was a red herring.

**"Unknown skill(s)" crash-loop — worker profiles missing skills referenced in `--skill` flags.** Workers crash with `Error: Unknown skill(s): <name>` when a ticket's `--skill` flag references a skill that doesn't exist in the worker profile's skills directory (`/root/.hermes/profiles/<name>/skills/`). This is a silent crash — zero useful output, exit code 1, repeats indefinitely.

**Diagnose:** `hermes kanban --board <board> log <task_id> | tail -5` — look for `Error: Unknown skill(s)`.

**Root cause:** Worker profiles have isolated skill directories. Adding a new skill to the main `/root/.hermes/skills/` does NOT propagate to profiles.

**Fix:**
```bash
# Sync ALL productivity skills to ALL active profiles
bash /root/.hermes/skills/productivity/knowledge-base/scripts/sync-to-profiles.sh
# Then reclaim the crashed tasks
hermes kanban --board <board> reclaim <task_id>
```

**Prevention:** Run `sync-to-profiles.sh` after: (a) installing a new skill, (b) editing any skill's SKILL.md/references/templates/scripts, (c) creating a new worker profile. The script syncs every skill under `productivity/` to every profile that already has a `skills/productivity/` directory. **Real case (2026-06-09):** planners crashed 54 times each on `book-extraction` because the skill was only in the main skills dir, not in the planner profile.

**Bundling independent lanes into one card.** If the user asks for two independent outcomes, create two cards. Example: "fix blockers and check model variants" is not one fixer task; create a fixer/engineer card for the fixes and an explorer/researcher card for the variant check, then optionally gate review on both.

**Over-linking because of wording.** "Finally check X" may still be parallel with implementation if X is static config, docs, or source discovery. Link it after implementation only when the check depends on the implementation result.

**Circular parent dependencies (deadlock).** Creating a review task with the coder task as `parent` while the coder task is blocked waiting for review creates a deadlock — the review task stays `todo` forever because its parent is `blocked` and the dispatcher won't promote children of blocked tasks. Fix: block the coder with `review-required`, then create the review task WITHOUT a `parent` link. Include the coder task ID in the review task's body text as a reference.

**Auto-unblock defeats manual blocks.** The dispatcher auto-promotes blocked tasks to `ready` when all parents are `done`. This means you cannot simply `hermes kanban block` a stuck task to free a slot — if its parents are done, the dispatcher unblocks it immediately. To stop a task from consuming a slot: either mark it `done` via SQL (`UPDATE tasks SET status='done' WHERE id='t_xxx'`), or remove its parent links first. When a task has posted a review-required handoff, it should be marked done and a standalone review task created — NOT left running or blocked. Real case (shop 2026-05-20): 2 tasks with review-required handoffs consumed worker slots for 7h; blocking them failed because parents were done; marking them done + creating standalone reviews freed the slots.

**Forgetting dependency links.** If the task graph says `research -> implement -> review`, do not create all tasks as independent ready cards. Use parent links so implement/review cannot run before their inputs exist.

**Stale parent→child links after archiving bundle tickets.** When you archive a bundle ticket that was a child of a root task, the root still lists it as a child in `task_links`. Run `hermes kanban unlink <root> <archived>` to clean up. Otherwise the graph shows dead references and confuses audits.

**Task timeout calibration.** Different task types need different `--max-runtime`. Research/web-heavy: 600–1000s. Install/download: 120–300s. Code implementation: default 180s usually fine. Always set at creation — don't wait for 5 watchdog cycles. Full data in `references/timeout-calibration.md`.

**Runtime tuning (profile vs per-task).** `max_runtime_seconds` in the profile config does NOT propagate to kanban tasks — each task has its own `max_runtime_seconds` column in `kanban.db`. `max_iterations` controls API call budget (default 50). Timeout loops are invisible to the block watchdog; the crash-loop watchdog (`check-crash-loops.py`) now detects them via run count and heartbeat staleness. 

**Fix recipe when tasks timeout repeatedly:**
```bash
# 1. Check the actual per-task runtime (not the profile config)
python3 -c "
import sqlite3
for board in ['the-swarm', 'videogame-lab', 'shop']:
    db = sqlite3.connect(f'/root/.hermes/kanban/boards/{board}/kanban.db')
    for r in db.execute('SELECT id, max_runtime_seconds FROM tasks WHERE status=\"running\"'):
        print(f'{board} {r[0]} max_runtime={r[1]}')
    db.close()
"

# 2. Fix: set per-task runtime + bump max_iterations in profile
python3 -c "
import sqlite3
boards = {'the-swarm': ['t_xxx'], 'videogame-lab': ['t_yyy']}
for board, tids in boards.items():
    db = sqlite3.connect(f'/root/.hermes/kanban/boards/{board}/kanban.db')
    for tid in tids:
        db.execute('UPDATE tasks SET max_runtime_seconds = 600 WHERE id = ?', (tid,))
    db.commit()
    db.close()
"
hermes config --profile coder set kanban.max_iterations 120
hermes config --profile planner set kanban.max_iterations 120

# 3. Reclaim to restart with new settings
hermes kanban --board <board> reclaim <id>
```

**Real case (2026-05-20):** planner on the-swarm and coder on videogame-lab both timed out at 120s despite profile `max_runtime_seconds: 600`. Root cause: the per-task DB column was `max_runtime_seconds = 120` and took precedence. 717 cumulative timeout runs across 3 tasks, all invisible to both watchdogs until `check-crash-loops.py` was upgraded with Phase 2 detection.

**Dispatcher DB corruption — silent dispatch failure (⚠️ DATA LOSS).** The default board's DB (`/root/.hermes/kanban.db`) can silently degrade to an empty file (4,096 bytes, 0 tables) after extended gateway uptime. Symptoms: `hermes kanban list` still shows tasks (ghost state — likely from an in-memory cache), but no workers spawn, and direct SQLite access returns zero tables. The dispatcher logs may show `no such table: kanban_notify_subs` or nothing at all.

**Fix:** `rm /root/.hermes/kanban.db && systemctl restart hermes-gateway`. ⚠️ **ALL default board tasks are lost** — the DB is recreated empty with fresh schema. The backup at `/root/.hermes/kanban.db.corrupt.*.bak` (if any exists from a prior integrity check) is a snapshot, not a recovery target. After restart, `hermes kanban list` should show `(no matching tasks)` and the DB should be ~100KB+ with all tables. **After restart, reclaim any ghost tasks** that the dispatcher may still think are running: `hermes kanban --board default list | grep '●' | awk '{print $2}' | while read id; do hermes kanban --board default reclaim "$id"; done`.

**Prevention:** The kanban DB integrity watchdog (`kanban-integrity-watchdog.py`, cron `b568a8418cf3`) checks every hour and alerts on corruption BEFORE the DB goes fully empty. Ensure this cron job is active.

**WAL mode → DELETE migration (corruption prevention).** SQLite WAL mode is vulnerable to checkpoint corruption on unclean shutdown. Hermes kanban DBs now use DELETE journal mode + FULL synchronous (patched in `kanban_db.py` May 2026). If you see WAL mode on a kanban DB, convert it and restart gateway. Full rationale and procedure in `references/kanban-db-corruption-recovery.md`.

**Budget exhaustion on migration/refactoring tasks.** When a task asks a worker to apply a migration AND re-verify the full test suite inline, the worker exhausts its iteration budget on test output (e.g. 90 iterations burned on 283 test logs in 95s). Fix: split verification from application. Reference prior benchmark results in the task body and explicitly tell workers to SKIP tests — CI will catch regressions. Seen on shop pnpm migration (2026-05-18): task blocked at 90/90 after 20min because it ran `pnpm test` inline despite a prior benchmark proving 283/283 pass.

**Reassignment vs. new task.** If a reviewer blocks with "needs changes," create a NEW task linked from the reviewer's task — don't re-run the same task with a stern look. The new task is assigned to the original implementer profile.

**Worker profiles can't access host dotfiles.** Each kanban worker profile has its own isolated `$HOME` (`/root/.hermes/profiles/<name>/home/`). Dotfiles like `~/.xurl`, `~/.gitconfig`, or `~/.config/gh/` set up on the host are invisible to workers. When a worker asks for OAuth setup that already works on the host, copy the dotfile to the profile's home. See `references/profile-home-isolation.md`.

**Argument order for links.** `kanban_link(parent_id=..., child_id=...)` — parent first. Mixing them up demotes the wrong task to `todo`.

**Don't pre-create the whole graph if the shape depends on intermediate findings.** If T3's structure depends on what T1 and T2 find, let T3 exist as a "synthesize findings" task whose own first step is to read parent handoffs and plan the rest. Orchestrators can spawn orchestrators.

- **Tenant inheritance — two modes.**

*Single-project session (HERMES_TENANT set in env):* Pass `tenant=os.environ.get("HERMES_TENANT")` on every `kanban_create` call so child tasks stay in the same namespace. Convenient when you only work on one project per session.

*Multi-project session (HERMES_TENANT NOT set, or ignored):* Pass `tenant="<project-name>"` as a literal string on every `kanban_create`. This lets you create tasks for `shop` and `music-library` in the same conversation without switching env vars. The dispatcher handles all tenants in parallel — no second Hermes instance needed.

Do NOT mix modes: if you read `HERMES_TENANT` for some cards and pass literals for others, you'll silently split tasks across tenants. Pick one mode for the session and stick to it.

**Unlinking a task from an archived parent promotes it to `ready` immediately.** When a parent is archived, the child loses its dependency and the dispatcher picks it up right away — even if you're about to link a replacement parent. Sequence: 1) Link the new parent FIRST, 2) Unlink the old parent SECOND. If a task was already dispatched (running), use `hermes kanban reclaim <id>` to reset it to `todo`, then verify it now waits for the correct parent. Note: `hermes kanban link <parent_id> <child_id>` and `hermes kanban unlink <parent_id> <child_id>` use positional arguments, NOT `--parent`/`--child` flags.

**`--board` flag goes BEFORE the subcommand.** `hermes kanban --board <slug> list` works; `hermes kanban list --board <slug>` fails with "unrecognized arguments." This applies to all kanban subcommands (create, archive, reclaim, unblock, etc.).

**`kanban boards switch` is unreliable for `list`.** The switch may report success but `kanban list` still shows the previous board. Always use explicit `--board <slug>` instead of relying on the switched state after `boards switch`.

**`archive` has no `--yes` flag.** Unlike `hermes profile delete --yes`, archive is non-interactive by default — just pass task IDs: `hermes kanban --board <board> archive <id1> <id2> ...`. **However**, `hermes kanban transition <id> archive` silently fails from `blocked` state — tasks remain blocked even though the command returns success. To archive blocked tasks, use direct SQL: `UPDATE tasks SET status='archived', completed_at=<unix_ts> WHERE id='<tid>';`. See `devops/disk-cleanup/references/kanban-db-schema.md`.

**Shell quoting breaks on complex `--body` content.** Em dashes (`—`), French accents, backticks, and single quotes defeat `shlex.quote()` when creating tasks.

**Workaround A (preferred — preserves full body):** Use `execute_code` to write the body to a temp file, then call `terminal()` with `$(cat /tmp/body.txt)`:
```python
from hermes_tools import write_file, terminal
write_file('/tmp/kanban_body.txt', body_content)
terminal(f'hermes kanban --board {board} create '
         f'--assignee {profile} --max-runtime 3600 '
         f'--body "$(cat /tmp/kanban_body.txt)" '
         f'"Task Title"')
```

**Workaround B (fallback — body-lite):** Create with `--title` and `--assignee` only; skip `--body`. Body content can be reconstructed from context or added later via `kanban comment`. Use this when execute_code is unavailable or the body is simple enough to reconstruct.

**`reclaim` does not support `--force`.** `hermes kanban reclaim <id> --force` errors with `unrecognized arguments: --force`. Reclaim stops the worker, kills the PID, and resets the task — there's no separate force mode. If reclaim says `not running or unknown id`, the task's status isn't `running` from the dispatcher's perspective, even if the DB column says `running`.

**Heartbeat NULL at task level is a false-positive zombie signal.** The `tasks.last_heartbeat_at` column can be NULL even on genuinely running tasks — it's only set after the worker's first heartbeat write, and new runs start with NULL. If a previous run crashed and the dispatcher reclaimed + respawned, the task-level heartbeat stays NULL from the old run. **Always cross-check `task_runs`**: check the current run's `started_at` and `last_heartbeat_at` before declaring a zombie. A task with NULL task-level heartbeat but a current run started 11 minutes ago is alive — not a zombie.

```python
# Query both task-level and run-level heartbeat state
import sqlite3, time
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
now = time.time()
t = conn.execute(
    "SELECT id, last_heartbeat_at, current_run_id FROM tasks WHERE status='running'"
).fetchall()
for tid, hb, run_id in t:
    task_hb_age = (now - hb) / 60 if hb else 999
    run = conn.execute(
        "SELECT started_at, last_heartbeat_at FROM task_runs WHERE id=? AND status='running'",
        (run_id,)
    ).fetchone()
    if run:
        run_age = (now - run[0]) / 60
        run_hb_age = (now - run[1]) / 60 if run[1] else run_age
        print(f"{tid}: task_hb={task_hb_age:.0f}m run_hb={run_hb_age:.0f}m run_age={run_age:.0f}m {'✅ ALIVE' if run_hb_age < 30 else '🧟 ZOMBIE'}")
```

**`reclaim` is single-task only.** `hermes kanban reclaim` accepts exactly one task ID per invocation. Passing multiple IDs (space-separated) produces `unrecognized arguments`. Loop over task IDs individually.

**`respawn_guarded` / `active_pr` — PR URLs in comments block dispatch for 24h.** The dispatcher scans `task_comments` for GitHub PR URLs (any repo, any state — open, merged, or closed). When found within `_RESPAWN_GUARD_PR_WINDOW` (86400s = 24h), it sets `active_pr` guard and refuses to spawn. The PR being merged/closed does NOT clear the guard — the comment persists. **Never post PR URLs in kanban comments.** Use GitHub labels instead: apply `kanban:TASK_ID` label to the PR, reference the label in block reasons and comments.

**Fix when tasks are stuck on `active_pr`:**
```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
# Find offending comments
rows = conn.execute(
    "SELECT id, task_id FROM task_comments WHERE body LIKE '%github.com%pull%'"
).fetchall()
# Delete them
conn.execute("DELETE FROM task_comments WHERE body LIKE '%github.com%pull%'")
conn.commit()
```
Tasks become spawnable on the next dispatcher tick after deletion.

**New board dispatcher claims all tasks instantly.** After creating tasks on a freshly-created board, its dispatcher loop picks them up within seconds — even if worker profiles are stopped. This produces a wave of crash/block events. Always `reclaim` all tasks on the new board after a bulk migration to reset them to `ready` (or `todo` if you want them held).

**Kanban notify subscriptions — zero by default.** No Telegram/Discord notifications are sent unless you explicitly subscribe. The gateway delivers events (`completed`, `blocked`, `promoted`, etc.) to subscribed channels via the `kanban_notify_subs` table. CLI: `hermes kanban notify-subscribe/unsubscribe/list`. Full schema, batch subscription SQL, and event type coverage in `references/kanban-notify.md`.

**Bulk unblock risks OOM on memory-constrained hosts.** When many tasks (20+) are unblocked simultaneously, the dispatcher may claim them all and spawn workers for each. Each worker loads a model (~120MB RSS), so 40 unblocked tasks → 40 workers → 4.8GB just for workers plus the gateway's own memory. On 8GB hosts, this OOMs instantly. **Fix: set `kanban.max_spawn` to cap concurrent workers** (see \"Controlling worker concurrency\" above). Without this config, unblock in small batches (5-10), wait for workers to finish or block, then unblock the next batch.

**Profile naming & cleanup**

**Profile naming — use generic profiles.** One profile per role, shared across all boards: `coder`, `researcher`, `reviewer`, `planner`. No project prefix. The hard requirement: tasks MUST have an assignee that matches an existing profile — unassigned tasks never run.

**Shared configs**: Worker profiles have isolated `$HOME` — shared config files (`.xurl`, `.gitconfig`) must be copied to each profile's home. See `references/shared-config-profiles.md` for the full recipe and impact of skipping this step.

**Cleanup flow** when you find orphaned or misnamed profiles:

1. `hermes profile list` — identify non-prefixed profiles
2. For each: check all boards for tasks assigned to it (`hermes kanban --board <b> list | grep <name>`)
3. If tasks exist → `hermes kanban --board <b> reassign <id> <generic-profile>` + `hermes profile delete <old> --yes`
4. If no tasks → `hermes profile delete <name> --yes`

**Creating a new project team**: create board first, then assign tasks to existing profiles (coder, reviewer, researcher, planner).

## Controlling worker concurrency (OOM prevention)

The dispatcher spawns one worker **per claimed task**, not per profile.
On a busy board with 40 ready tasks and 5 profiles, the dispatcher may
spawn 20+ workers simultaneously — each ~120MB RSS — pushing an 8GB host
into OOM. The fix is `kanban.max_spawn`, a **live concurrency cap** that
counts already-running tasks against the limit:

```bash
# Limit total concurrent workers per board (NOT all boards combined)
hermes config set kanban.max_spawn 2
# REQUIRED: restart gateway for the change to take effect
hermes gateway restart
```

```yaml
# config.yaml
kanban:
  max_spawn: 2   # at most 2 workers running at once per board
```

With `max_spawn=2` and 2 active profiles, each profile gets at most 1
worker — the dispatcher keeps excess ready tasks queued until a slot
frees up. Recommend setting to slightly below your number of active profiles
(e.g. 3 profiles → `max_spawn=2`) to leave headroom. The default is `None` (unlimited).
Gateway restart is mandatory — the config is read once at startup.

**Verification:** after restart, `ps aux | grep "hermes.*kanban"` should
show at most `max_spawn` workers **per board**, and `free -h` should show healthy memory.
With 10 boards and `max_spawn=5`, up to 50 concurrent workers is expected — not a bug.

**⚠️ Pitfall:** `max_spawn` only limits **new** spawns. Tasks already `running`
before the config change or gateway restart keep their claims until TTL expires
(~15 min). After any `max_spawn` change or gateway restart, reclaim all running
tasks to reset them:

**⚠️ Pitfall — same-tick overspawn:** the dispatcher computes `running_count`
(`SELECT COUNT(*) FROM tasks WHERE status='running'`) once at the start of each
tick, before the spawn loop. If a single tick sees many `ready` tasks and
`running_count` is low (e.g. 0 or 1), the spawn loop checks `running_count +
spawned >= max_spawn` but does NOT re-query after each spawn. Under rapid task
promotion or when multiple boards share the same tick window, this can produce
more workers than `max_spawn` allows. **Observed 2026-05-20:** shop board,
`max_spawn=5`, gateway restarted at 02:46 with the config in effect, yet 7
workers were running at 08:28 — 6 spawned in a 2-second window (08:28:55–57)
from the same dispatcher tick. DB showed `running_count=1` (t_16f50502 from
08:26:29) yet 6 more were spawned, totaling 7 > 5. Full evidence and code
walkthrough in `references/max-spawn-overspawn-bug.md`.

```bash
hermes kanban --board <board> list | grep "●" | awk '{print $2}' | while read id; do
  hermes kanban --board <board> reclaim "$id"
done
```

**Root-cause insight (why OOM happens even with free swap):** On systemd-managed
hosts, the gateway cgroup shows `MemorySwapCurrent=0` even when system-wide swap
is available. When 40 workers spawn simultaneously, they allocate RAM faster
than the kernel can swap — the OOM killer terminates the largest consumer
(gateway) before swap is fully utilized. `max_spawn` prevents the allocation
storm, giving the kernel time to manage memory gracefully.

When a worker profile keeps crashing or getting blocked, the kanban dashboard flags the task with a ⚠ badge and opens a **Recovery** section in the drawer. Three primary actions:

1. **Reclaim** (or `hermes kanban reclaim <task_id>`) — abort the running worker immediately and reset the task to `ready`. The existing claim TTL is ~15 min; this is the fast path out.
2. **Reassign** (or `hermes kanban reassign <task_id> <new-profile> --reclaim`) — switch the task to a different profile (one that exists on this setup) and let the dispatcher pick it up with a fresh worker.
3. **Change profile model** — the dashboard prints a copy-paste hint for `hermes -p <profile> model` since profile config lives on disk; edit it in a terminal, then Reclaim to retry with the new model.

**Important: `reclaim` vs `unblock`.** `hermes kanban reclaim` only works on `running` tasks — it forcibly terminates the worker and resets to `ready`. For `blocked` tasks, you must `hermes kanban unblock <id>` first. If you need to reassign a blocked task: unblock → reassign --reclaim → done. Sequence matters.

**Deleting profiles:** Use `hermes profile delete <name> --yes`. Piping `echo 'y'` through stdin does NOT work — the confirmation prompt requires the `--yes` flag. Always verify with `hermes profile list` after deletion.

**Before any recovery: diagnose the crash properly.** Load the `kanban-worker` skill and follow `references/diagnosing-crashes.md`. The most common causes by far:
- **No swap** on memory-constrained hosts (OOM killer)
- **Gateway restart cascade** (one OOM kills gateway, all workers die as collateral)
- **NOT the task being too complex** — splitting should be the last resort, not the first reflex.

**Hallucination warnings appear on tasks where a worker's `kanban_complete(created_cards=[...])` claim included card ids that don't exist or weren't created by the worker's profile (the gate blocks the completion), or where the free-form summary references `t_<hex>` ids that don't resolve (advisory prose scan, non-blocking). Both produce audit events that persist even after recovery actions — the trail stays for debugging.

**Deep tasks (research, analysis) need `--max-runtime` set at creation.** The dispatcher default timeout is 180s. Web-search-heavy research tasks routinely hit 180-200s and time out before producing output. The watchdog will unblock and retry, but the task hits the same wall every time (observed: 5 consecutive timeouts at ~190s on the-swarm UX research, 2026-05-19).

**⚠️ MANDATORY: set `--max-runtime` on EVERY task.** The profile config `max_runtime_seconds` does NOT propagate to kanban tasks — each task has its own DB column. NULL defaults to a hardcoded fallback (~120s) which is too low for most work. Use the calibration table below. A 30-second CLI flag prevents hours of timeout loops and watchdog escalations.

| Task type | `--max-runtime` | `max_iterations` |
|-----------|----------------|-------------------|
| All tasks | 3600s (1h safety net) | 120 |

**Heartbeat is the primary liveness signal.** Workers heartbeating regularly should NOT be killed. `max_runtime_seconds` = 3600s is a generous safety net for actual runaway loops — not a performance target. The dispatcher's `dispatch_stale_timeout_seconds` (4h, with heartbeat required within 1h) handles genuinely stuck workers.

**Fix at creation time — don't wait for 5 watchdog cycles.** The `--max-runtime` flag on `hermes kanban create` sets the per-task DB column that the dispatcher actually enforces.

```bash
# ✅ Always include --max-runtime
hermes kanban --board <board> create --assignee coder --max-runtime 600s "My task"

# ❌ No max-runtime = task will timeout at 120s silently
hermes kanban --board <board> create --assignee coder "My task"
```

**Fix:** create research/synthesis/large-scope tasks with `--max-runtime 300s` minimum. For deep research that reads multiple sources, use `1000s` and calibrate down from the actual runtime afterward.

```bash
# Deep research (safe upper bound, then check actual runtime to tune)
hermes kanban --board <board> create --assignee researcher --max-runtime 1000s "Research: ..."

# Light research / code analysis
hermes kanban --board <board> create --assignee researcher --max-runtime 300s "Research: ..."
```

**There is no `kanban update` to change an existing task's runtime.** If a task was created without `--max-runtime` and keeps timing out, the pattern is: archive → recreate with the flag → reclaim child tasks (they were auto-promoted to ready when the parent was archived) → re-link them to the new parent. Full recipe in `references/deep-task-timeout-recovery.md`.

**🎯 Strategy:** set 3600s (1h) by default. The heartbeat handles liveness — `max_runtime` is only a safety net for runaway loops. Over-estimating is safe and prevents false-positive timeouts.

**`kanban create` syntax note:** title is a positional argument, NOT `--title`. This trips up agents coming from `gh issue create` conventions.

```bash
# ✅ Correct
hermes kanban create --assignee coder --priority 1 "My Title Here"

# ❌ Wrong — errors with "unrecognized arguments: --title"
hermes kanban create --title "My Title" --assignee coder  # does not work
```

The full flag set: `--assignee`, `--priority`, `--body`, `--parent` (repeatable), `--max-runtime`, `--max-retries`, `--workspace`, `--tenant`, `--triage`, `--idempotency-key`, `--skill`, `--json`. Positional `title` always comes last.

**Kanban DB architecture & disaster recovery:** See `references/kanban-db-architecture.md` — two-tier architecture (dispatcher DB vs per-board DBs), corruption diagnosis, safe deletion, and header-fix recovery. Dispatcher DB is a coordination cache; all real data lives in board DBs.

**Board health check (manual diagnostics)**

When the user asks "what's working?" or you suspect silent failures, follow the 5-step health check in `references/kanban-health-check.md`: boards overview → list running → show event history → verify worker PIDs → check diagnostics. The quick one-liner at the bottom of that reference produces a full table of running tasks × worker PID status across all boards in one shot.

**⚠️ Always start with Step 0 (DB integrity check) before any health audit. A corrupted dispatcher DB silently disables dispatch and can lose all tasks when the gateway auto-rebuilds it empty.** Full corruption investigation and recovery procedure in `references/kanban-db-corruption-recovery.md`.

**Web dashboard:** `hermes dashboard --host 0.0.0.0 --insecure --skip-build` (port 9119). See `references/dashboard.md` for full setup. The dashboard provides a visual board view with task details, recovery actions, and diagnostics — use it when the user wants to "see" the boards rather than CLI output.

**CI-gated PR workflow:** For repos with GitHub Actions CI, use the label-based CI-watchdog pattern (`references/ci-watchdog.md`) instead of PR URLs in comments. Workers create PRs with `kanban:TASK_ID` labels; a cron watchdog merges green PRs. Avoids the 24h `active_pr` guard.

**Pre-spawn health watchdog:** Scans all boards for tasks with dispatch-blocking issues (NO-ASSIGNEE, PR-URL-COMMENTS, PR-URL-IN-BODY, STUCK-SCHEDULED, NO-BODY, NO-ASSIGNEE-BLOCKED). NO-SKILLS and NO-MRT checks retired May 2026 — dispatcher injects skills at spawn, heartbeat-first with 3600s safety net. Notification-only, no modification. See `references/pre-spawn-health-watchdog.md` for full schema and script location.

**⛔ Workflow `name` MUST be `CI` — exact match.** The branch protection rule `contexts: ["CI"]` requires a check literally named `CI`. If the workflow is named `🚀 Deploy` (or anything else), `gh pr merge` fails even when all jobs are green, causing an infinite loop: merge fails → unblock → coder respawns → re-blocks → merge fails again. **Fix:** rename `name: 🚀 Deploy` to `name: CI` in `.github/workflows/deploy.yml` (or equivalent). Real case (shop + music-library 2026-05-20): both had `name: 🚀 Deploy`. All project repos verified 2026-05-20. See `references/ci-watchdog.md` for the full branch protection recipe and BOARD_REPOS verification table.

### Proactive recovery: Block Watchdog

Instead of waiting for a human to notice stuck tasks in the dashboard, set up a **cron-based block watchdog** that scans all boards every 5 minutes, identifies tasks blocked by technical failures (crashes, OOM, iteration budget exhausted), and unblocks them automatically. Review-required and dependency-gate blocks are left alone. Uses a two-scanner wrapper (`~/.hermes/scripts/watchdog-all.py`) that runs `check-blocked-tasks.py` (blocked tasks, 30s timeout, always exits 0) + `check-crash-loops.py` (running tasks with ≥5 consecutive failures — invisible to the block scanner). An LLM agent classifies findings and acts. Full setup — scripts, cron config, classification rules, crash-loop auto-block — in `references/block-watchdog.md`.

**Pre-Spawn Health Watchdog**

A no-agent watchdog that scans all boards for tasks with dispatch-blocking issues
(NO-ASSIGNEE, PR-URL-COMMENTS, PR-URL-IN-BODY, STUCK-SCHEDULED, BODY-IS-NULL, NO-ASSIGNEE-BLOCKED).
Silent when clean. Full schema and setup in `references/pre-spawn-health-watchdog.md`.
Script: `~/.hermes/scripts/pre-spawn-watchdog.py`.

**Kanban DB Integrity Watchdog**

A no-agent watchdog that runs `PRAGMA integrity_check` on all kanban DBs every hour.
Silent when clean (exit 0). On corruption, backs up the corrupt DB and alerts via cron delivery.
Cron: `b568a8418cf3` (schedule: `0 * * * *`). Script: `scripts/kanban-integrity-watchdog.py`.
Full corruption recovery procedure: `references/kanban-db-corruption-recovery.md`.
