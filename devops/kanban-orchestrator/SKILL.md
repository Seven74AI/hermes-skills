---
name: kanban-orchestrator
description: Decomposition playbook + anti-temptation rules for an orchestrator profile routing work through Kanban. The "don't do the work yourself" rule and the basic lifecycle are auto-injected into every kanban worker's system prompt; this skill is the deeper playbook when you're specifically playing the orchestrator role.
version: 4.1.0
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
- **Run independent lanes in parallel.** If two cards do not need each other's output, leave them unlinked so the dispatcher can fan them out. Link only true data dependencies.
- **Never create dependent work as independent ready cards.** If a card must wait for another card, pass `parents=[...]` in the original `kanban_create` call. Do not create it first and link it later, and do not rely on prose like "wait for T1" inside the body.
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

**Split-and-merge for complex monolithic tasks:** When a single task does too many unrelated fixes that COULD run in parallel, split it (see `references/dependency-update-pipeline.md`).

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

**Board migration (moving tasks between boards):** When a tenant's tasks are on the wrong board (e.g. `music-library` tasks on `default`), use the recreate+archive pattern: reclaim/unblock → recreate on target board → archive on source. Step-by-step recipe, CLI pitfalls (`--board` position, board switch unreliability, shell quoting), and parent/child link handling in `references/board-migration.md`.

**Team creation from scratch:** When the user wants a new specialist AI agent team (profiles, Kanban board, GitHub repo, Notion page, cron jobs), follow the full 7-step recipe in `references/team-creation-checklist.md`. Covers: roster design, profile creation, SOUL.md authoring, infrastructure setup, task decomposition, recurring jobs, and verification.

**Phased dependency update pipeline:** For large npm dep updates (20+ packages, major jumps), decompose into a 6-task chain: research (parallel) → minors → likely-safe majors → risky majors → known-breaking → verification. Full task graph, phase details, package categorization, and advanced split-and-merge pattern in `references/dependency-update-pipeline.md`.

## Pitfalls

**Reaching for external tools before checking internal Kanban.** If a user asks to set up a team, project, or multi-agent workflow, the Hermes Kanban system (profiles + dispatcher) is the first tool to consider — not Linear, Jira, Notion, or any external SaaS. Load this skill before suggesting external tools.

**Inventing profile names that don't exist.** The dispatcher silently fails to spawn unknown assignees — the card just sits in `ready` forever. Always assign to a profile from your Step 0 discovery; ask the user if you're unsure.

**Unassigned tasks (no assignee at all).** Tasks created without an `--assignee` sit in `ready` forever — the dispatcher only claims tasks that have a valid assignee. This is different from wrong-assignee (above): here the task was never assigned to anyone. When you see `(unassigned)` on a board, the tasks will never run. Fix: batch-reassign them to a valid profile.

```bash
# Batch-reassign all unassigned ready tasks to a profile
hermes kanban --board <board> list 2>&1 | grep 'unassigned' | awk '{print $2}' | while read id; do
  hermes kanban --board <board> reassign "$id" <profile> --reclaim
done
```

**Real case (2026-05-19):** hermes-skills board had 19 `ready` tasks all `(unassigned)` — zero progress until batch-reassigned to `coder`. After reassignment, the dispatcher picked them up within seconds.

**Bundling independent lanes into one card.** If the user asks for two independent outcomes, create two cards. Example: "fix blockers and check model variants" is not one fixer task; create a fixer/engineer card for the fixes and an explorer/researcher card for the variant check, then optionally gate review on both.

**Over-linking because of wording.** "Finally check X" may still be parallel with implementation if X is static config, docs, or source discovery. Link it after implementation only when the check depends on the implementation result.

**Circular parent dependencies (deadlock).** Creating a review task with the coder task as `parent` while the coder task is blocked waiting for review creates a deadlock — the review task stays `todo` forever because its parent is `blocked` and the dispatcher won't promote children of blocked tasks. Fix: block the coder with `review-required`, then create the review task WITHOUT a `parent` link. Include the coder task ID in the review task's body text as a reference.

**Forgetting dependency links.** If the task graph says `research -> implement -> review`, do not create all tasks as independent ready cards. Use parent links so implement/review cannot run before their inputs exist.

**Task timeout calibration.** Different task types need different `--max-runtime`. Research/web-heavy: 600–1000s. Install/download: 120–300s. Code implementation: default 180s usually fine. Always set at creation — don't wait for 5 watchdog cycles. Full data in `references/timeout-calibration.md`.

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

**Shell quoting breaks on complex `--body` content.** Em dashes (`—`), French accents, backticks, and single quotes defeat `shlex.quote()` when creating tasks. Workaround: recreate with `--title` and `--assignee` only; skip `--body`. Body content can be reconstructed from context or added later via `kanban comment`.

**`reclaim` is single-task only.** `hermes kanban reclaim` accepts exactly one task ID per invocation. Passing multiple IDs (space-separated) produces `unrecognized arguments`. Loop over task IDs individually.

**New board dispatcher claims all tasks instantly.** After creating tasks on a freshly-created board, its dispatcher loop picks them up within seconds — even if worker profiles are stopped. This produces a wave of crash/block events. Always `reclaim` all tasks on the new board after a bulk migration to reset them to `ready` (or `todo` if you want them held).

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
show at most `max_spawn` workers, and `free -h` should show healthy memory.

**⚠️ Pitfall:** `max_spawn` only limits **new** spawns. Tasks already `running`
before the config change or gateway restart keep their claims until TTL expires
(~15 min). After any `max_spawn` change or gateway restart, reclaim all running
tasks to reset them:

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

**Fix:** create research/synthesis/large-scope tasks with `--max-runtime 300s` minimum. For deep research that reads multiple sources, use `1000s` and calibrate down from the actual runtime afterward.

```bash
# Deep research (safe upper bound, then check actual runtime to tune)
hermes kanban --board <board> create --assignee researcher --max-runtime 1000s "Research: ..."

# Light research / code analysis
hermes kanban --board <board> create --assignee researcher --max-runtime 300s "Research: ..."
```

**There is no `kanban update` to change an existing task's runtime.** If a task was created without `--max-runtime` and keeps timing out, the pattern is: archive → recreate with the flag → reclaim child tasks (they were auto-promoted to ready when the parent was archived) → re-link them to the new parent. Full recipe in `references/deep-task-timeout-recovery.md`.

**🎯 Strategy:** over-estimate (1000s), let the task finish, check `hermes kanban show <id> | grep elapsed` for actual runtime, then use that to calibrate future tasks of the same class. The user explicitly preferred this approach: "met genre 1000 comme ça on est sûr que ça passe, et on regardera combien de temps la tâche a pris pour adapter pour la suite."

**`kanban create` syntax note:** title is a positional argument, NOT `--title`. This trips up agents coming from `gh issue create` conventions.

```bash
# ✅ Correct
hermes kanban create --assignee coder --priority 1 "My Title Here"

# ❌ Wrong — errors with "unrecognized arguments: --title"
hermes kanban create --title "My Title" --assignee coder  # does not work
```

The full flag set: `--assignee`, `--priority`, `--body`, `--parent` (repeatable), `--max-runtime`, `--max-retries`, `--workspace`, `--tenant`, `--triage`, `--idempotency-key`, `--skill`, `--json`. Positional `title` always comes last.

### Board health check (manual diagnostics)

When the user asks "what's working?" or you suspect silent failures, follow the 5-step health check in `references/kanban-health-check.md`: boards overview → list running → show event history → verify worker PIDs → check diagnostics. The quick one-liner at the bottom of that reference produces a full table of running tasks × worker PID status across all boards in one shot.

### Proactive recovery: Block Watchdog

Instead of waiting for a human to notice stuck tasks in the dashboard, set up a **cron-based block watchdog** that scans all boards every 5 minutes, identifies tasks blocked by technical failures (crashes, OOM, iteration budget exhausted), and unblocks them automatically. Review-required and dependency-gate blocks are left alone. Uses a data-collection script (`~/.hermes/scripts/check-blocked-tasks.py`, 30s timeout per command, always exits 0) + LLM agent for classification. Full setup — script, cron config, classification rules — in `references/block-watchdog.md`.
