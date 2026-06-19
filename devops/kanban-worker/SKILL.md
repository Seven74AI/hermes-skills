---
name: kanban-worker
description: Pitfalls, examples, and edge cases for Hermes Kanban workers. The lifecycle itself is auto-injected into every worker's system prompt as KANBAN_GUIDANCE (from agent/prompt_builder.py); this skill is what you load when you want deeper detail on specific scenarios.
version: 2.4.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [kanban, multi-agent, collaboration, workflow, pitfalls]
    related_skills: [kanban-orchestrator]
---

# Kanban Worker — Pitfalls and Examples

> You're seeing this skill because the Hermes Kanban dispatcher spawned you as a worker with `--skills kanban-worker` — it's loaded automatically for every dispatched worker. The **lifecycle** (6 steps: orient → work → heartbeat → block/complete) also lives in the `KANBAN_GUIDANCE` block that's auto-injected into your system prompt. This skill is the deeper detail: good handoff shapes, retry diagnostics, edge cases.

## Workspace handling

Your workspace kind determines how you should behave inside `$HERMES_KANBAN_WORKSPACE`:

| Kind | What it is | How to work |
|---|---|---|
| `scratch` | Fresh tmp dir, yours alone | Read/write freely; it gets GC'd when the task is archived. |
| `dir:<path>` | Shared persistent directory | Other runs will read what you write. Treat it like long-lived state. Path is guaranteed absolute (the kernel rejects relative paths). |
| `worktree` | Git worktree at the resolved path | If `.git` doesn't exist, run `git worktree add <path> <branch>` from the main repo first, then cd and work normally. Commit work here. |

## ⛔ TOKEN ECONOMY — 90 TURNS, DON'T WASTE THEM

You have ~90 turns (iterations) per run. Every tool call burns 1 turn. When you
hit the limit, the gateway kills you with "iteration budget exhausted" — your
work is LOST and the watchdog restarts you from zero. **This is the #1 cause of
wasted kanban runs across all boards.**

### The ONE rule: background+wait for ALL heavy work

```
# ❌ NEVER — burns 50-200 turns on output lines
terminal("npx vitest run")
terminal("npx playwright test")
terminal("npm run build")
terminal("godot4 --headless --quit --path .")

# ✅ ALWAYS — burns 2-3 turns total
terminal("npm test && npm run build", background=true, notify_on_complete=true)
process(action="wait", timeout=3600)    # ← blocks WITHOUT burning turns
read_file("test-results.json")
```

`process wait` is a single call that passively blocks — no polling, no
sleep-loop. **One `process wait` replaces 50-100 polling iterations.**

**⛔ Watchdog awareness:** `process wait` blocks the agent loop, so the worker
can't heartbeat. The Block Watchdog's timeout-loop detection may flag this as
"stuck." The fix (`check-crash-loops.py`, 2026-06-18) checks claim extensions
(`pid_alive` events from the dispatcher) before auto-blocking — if a claim was
extended after the last heartbeat, the worker is alive and should be skipped.
Full diagnosis and the claim system explanation:
`references/watchdog-claim-interaction.md`.

### Anti-patterns that kill your budget

| ❌ Death pattern | ✅ Life pattern |
|-----------------|-----------------|
| `terminal("npm test")` inline | `terminal("npm test", background=true)` + `process wait` |
| `while sleep 10; do tail log; done` (1 turn/poll) | `process(action="wait")` (0 turns) |
| `for f in *.ts; do read_file "$f"; done` (1 turn/file) | `search_files` or batch reads |
| Read 5 web pages one-by-one | `web_extract(urls=[...])` — 5 pages in 1 turn |
| "Let me just run the tests real quick" inline | STOP. Background+wait. Every. Time. |

### Multi-step iteration → self-contained script

If your task needs test→fix→retest→fix cycles, write a SINGLE bash script that
does ALL the work internally, call it ONCE with background+wait. The worker uses
3 turns instead of 30. See `templates/e2e-iteration-loop.sh` for a starter.

### Budget checkpoints

- **30 turns (33%)** — heartbeat with "budget OK, X% used"
- **60 turns (66%)** — ⛔ STOP immediately. Trigger the Memento Pattern: load the `handoff` skill, create a structured handoff document (see Memento Pattern below), then block with `kanban_block(reason="budget checkpoint: handoff created")`. Partial work + clean block > dead worker.
- **75+ turns** — you're about to die. Push to git NOW, block immediately.

**IMPORTANT: Turn budget ≠ Token budget (Smart/Dumb Zone).** These checkpoints track *iteration count*, not token accumulation. Matt Pocock's "smart zone" concept (~100K tokens) is about the LLM's attention window degrading — a completely different failure mode. A worker doing `background=true` + `process wait` burns very few tokens but still accumulates turns via heartbeats. Hitting the 60-turn checkpoint does NOT mean the worker is in the dumb zone — it may have a tiny context. Conversely, a worker that opens 10 large files in 20 turns can enter the dumb zone well before any turn checkpoint fires. The checkpoint system is a safety net against iteration exhaustion, NOT a token-budget guard. See `references/smart-zone-vs-turn-budget.md` for the full analysis and Matt Pocock's original recommendations from the hermes-ops audit.

### Real case: t_8228590c on the-swarm (2026-05-20)

Three consecutive runs failed identically — the worker ran Playwright E2E tests
inline every time:
- Run #571: 90/90 exhausted after 58min → killed
- Run #573: protocol violation crash (worker finished but forgot complete/block)
- Run #579: SAME mistake, idle 36min with no heartbeat → reclaimed
- **3 runs, ~3h wasted, zero progress.** The worker's SOUL.md now has this
  section verbatim. Don't be run #580.

### Memento Pattern — structured handoff at budget checkpoints

When you hit the 60% budget checkpoint, don't just block — create a structured
"memento" for the next worker. This is the **Memento Pattern**: a formalized
handoff that lets a fresh worker resume exactly where you left off.

**Step-by-step:**

1. **Load the `handoff` skill:** `skill_view(name="handoff")` — follow its template
2. **Create a handoff document** in the workspace (write to `handoff.md`):
   - Current task state: what's done, what's in progress
   - Key files changed (paths only — do NOT paste full file contents)
   - Branch name and PR URL (if any)
   - Explicit next steps for the next worker
   - **Do NOT duplicate** content from PRDs, ADRs, design docs, or tickets —
     reference them by absolute path or URL instead. The handoff is a pointer, not
     a copy. Duplication creates staleness: the PRD updates, the handoff stays frozen.
3. **Push everything to git:** `git add -A && git commit -m "memento: budget checkpoint at ~60 turns" && git push origin $BRANCH`
4. **Block:** `kanban_block(reason="budget checkpoint: handoff created — next worker: read handoff.md in workspace, checkout $BRANCH, continue from Next steps")`

**Why structured handoff > bare block:**

| Bare block | Memento Pattern |
|------------|-----------------|
| Next worker sees "budget warning: partial X" — no context | Next worker has exact file list, branch, next steps |
| Worker re-discovers state from git + comments (10-15 turns) | Worker resumes in 2-3 turns |
| Repeated budget exhaustion = repeated rediscovery | Each handoff advances the task |
| Progress lost between runs | Progress checkpointed between runs |

The `handoff` skill's "reference, don't duplicate" rule is critical here — it prevents
the memento from accumulating stale content. Every artifact referenced (PRD, ADR, ticket
body) is the canonical source; the memento is just a trail of breadcrumbs.

**Matt Pocock's guidance:** clean resets via structured handoffs beat compacting because
compacting accumulates "sediments" of errors across runs. A fresh worker with a clear
memento makes better decisions than a worker reading stale mid-conversation context.

## Tenant isolation

If `$HERMES_TENANT` is set, the task belongs to a tenant namespace. When reading or writing persistent memory, prefix memory entries with the tenant so context doesn't leak across tenants:

- Good: `business-a: Acme is our biggest customer`
- Bad (leaks): `Acme is our biggest customer`

## Good summary + metadata shapes

The `kanban_complete(summary=..., metadata=...)` handoff is how downstream workers read what you did. Patterns that work:

**Coding task:**
```python
kanban_complete(
    summary="shipped rate limiter — token bucket, keys on user_id with IP fallback, 14 tests pass",
    metadata={
        "changed_files": ["rate_limiter.py", "tests/test_rate_limiter.py"],
        "tests_run": 14,
        "tests_passed": 14,
        "decisions": ["user_id primary, IP fallback for unauthenticated requests"],
    },
)
```

**Coding task that needs CI-gated review — use label-based PR workflow.**

For code changes that need CI verification before merge, use the label-based PR
pattern. The full workflow (fork model, direct model, review-gated alternative)
is documented in `kanban-project-workflow`. Quick reference:

1. Push branch, create PR on fork with label: `gh pr create --label "kanban:$HERMES_KANBAN_TASK"`
2. Block with: `kanban_block(reason="awaiting CI: PR label kanban:$HERMES_KANBAN_TASK")`
3. CI-watchdog merges if green, unblocks you
4. Respawn → verify merge → `kanban_complete`

NEVER post GitHub PR URLs in comments — triggers `respawn_guarded: active_pr` for 24h.

**Coding task that needs review — DO NOT JUST BLOCK. Create the reviewer task THEN block.**

For code-changing tasks that need review, you MUST create a reviewer task BEFORE blocking yourself. Otherwise the task sits blocked forever with nobody to review it. The pattern:

1. Post your handoff metadata as a comment
2. **Create a reviewer task** assigned to the appropriate reviewer profile (e.g. `music-reviewer`, `twitter-reviewer`, `shop-reviewer`, `reviewer`) with your task as parent
3. Block yourself with `review-required: `

```python
import json

# 1. Post the handoff
kanban_comment(
    body="review-required handoff:\n" + json.dumps({
        "changed_files": ["rate_limiter.py", "tests/test_rate_limiter.py"],
        "tests_run": 14,
        "tests_passed": 14,
        "diff_path": "/path/to/worktree",
        "decisions": ["user_id primary, IP fallback for unauthenticated requests"],
    }, indent=2),
)

# 2. Create reviewer task — WITHOUT parent (parent prevents dispatch — deadlock).
#    Include the coder task ID in the title for traceability.
reviewer_profile = "reviewer"  # ALWAYS the literal string "reviewer" — the profile name, not project-prefixed
kanban_create(
    title=f"Review: (t_{os.environ['HERMES_KANBAN_TASK']}) <summary>",
    assignee=reviewer_profile,
    body="Review the work from the coder task. Check the tests, the diff, and the handoff comment.",
    priority=int(os.environ.get("HERMES_KANBAN_PRIORITY", 5)) + 1,
)

# 3. Only NOW block
kanban_block(
    reason="review-required: rate limiter shipped, 14/14 tests pass — reviewer task created",
)
```

**How the reviewer handles it:** The reviewer reads your comment, reviews the work, and picks one of three outcomes:

- **Approves** → unblocks you with `hermes kanban unblock <id>` AND completes their own task with `kanban_complete(metadata={"approved": true})`
- **Requests changes** → comments on your task with feedback, blocks themselves with `needs changes: <summary>`, and creates a fix task assigned to the coder. The fix task completes → coder re-blocks review-required → watchdog re-promotes the reviewer.
- **Rejects** → the approach is fundamentally wrong (not fixable with small changes). Complete with `kanban_complete(metadata={"approved": false, "reason": "..."})` and optionally archive the coder task. The coder task stays blocked — human operator must decide whether to archive and recreate.

The watchdog (block-watchdog cron) handles the "reviewer blocked after creating fix" case (rule 3): when the fix coder completes, the watchdog detects the reviewer is blocked waiting and unblocks it for re-review.

If the reviewer profile doesn't exist on this machine, use the generic `reviewer` profile.

**⛔ Design-gate tasks: when the user wants manual approval BEFORE implementation.** Some tasks are explicitly "design only" — the user wants to review the design document themselves before ANY code is written. Detect this from explicit blocking language in the task body: "do NOT implement", "design only", "wait for user approval", "feu vert", "green light", "ne rien implémenter avant mon GO", "AUCUNE implémentation". In this case:

1. **Do NOT use the `review-required` / reviewer-task pattern.** Creating a reviewer task will lead the reviewer to auto-approve and spawn implementation tickets — exactly what the user doesn't want. The standard reviewer pattern (approve → unblock coder + auto-create next phase) is designed for implementation review, not human-gated design review.
2. **Instead:** produce the design artifact, then `kanban_block(reason="design complete — awaiting user review before implementation. Do NOT auto-spawn implementation tickets.")`. No reviewer task, no child tasks.
3. **As a reviewer who receives a design-review task:** when the parent design task's body contains design-gate language, do NOT auto-create implementation tickets. Approve or request changes on the design itself only, and note "user must approve before Phase 1" in your summary. Creating implementation tickets from a gated design review defeats the gate.

**Real case (2026-06-09):** hermes-ops board, MCP KB design task explicitly said "Ce ticket est UNIQUEMENT pour produire le document de design. Ne rien implémenter. Le user veut lire le rapport d'abord et décider ensuite." The worker used the standard review-required pattern → reviewer auto-approved and created Phase 1 implementation (t_0cafeeb3, 1,351 lines of Python) → user had to archive all 6 MCP tickets and recreate on a different board. The gate was in the task body but the worker ignored it in favor of the standard reviewer flow.

Use `kanban_complete` only when the task is genuinely terminal — e.g. a one-line typo fix, a docs change with no functional consequences, or a research task where the artifact IS the writeup itself.

**Research task:**
```python
kanban_complete(
    summary="3 competing libraries reviewed; vLLM wins on throughput, SGLang on latency, Tensorrt-LLM on memory efficiency",
    metadata={
        "sources_read": 12,
        "recommendation": "vLLM",
        "benchmarks": {"vllm": 1.0, "sglang": 0.87, "trtllm": 0.72},
    },
)
```

**Review task:**
```python
kanban_complete(
    summary="reviewed PR #123; 2 blocking issues found (SQL injection in /search, missing CSRF on /settings)",
    metadata={
        "pr_number": 123,
        "findings": [
            {"severity": "critical", "file": "api/search.py", "line": 42, "issue": "raw SQL concat"},
            {"severity": "high", "file": "api/settings.py", "issue": "missing CSRF middleware"},
        ],
        "approved": False,
    },
)
```

Shape `metadata` so downstream parsers (reviewers, aggregators, schedulers) can use it without re-reading your prose.

## Claiming cards you actually created

If your run produced new kanban tasks (via `kanban_create`), pass the ids in `created_cards` on `kanban_complete`. The kernel verifies each id exists and was created by your profile; any phantom id blocks the completion with an error listing what went wrong, and the rejected attempt is permanently recorded on the task's event log. **Only list ids you captured from a successful `kanban_create` return value — never invent ids from prose, never paste ids from earlier runs, never claim cards another worker created.**

```python
# GOOD — capture return values, then claim them.
c1 = kanban_create(title="remediate SQL injection", assignee="security-worker")
c2 = kanban_create(title="fix CSRF middleware", assignee="web-worker")

kanban_complete(
    summary="Review done; spawned remediations for both findings.",
    metadata={"pr_number": 123, "approved": False},
    created_cards=[c1["task_id"], c2["task_id"]],
)
```

```python
# BAD — claiming ids you don't have captured return values for.
kanban_complete(
    summary="Created remediation cards t_a1b2c3d4, t_deadbeef",  # hallucinated
    created_cards=["t_a1b2c3d4", "t_deadbeef"],                   # → gate rejects
)
```

If a `kanban_create` call fails (exception, tool_error), the card was NOT created — do not include a phantom id for it. Retry the create, or omit the id and mention the failure in your summary. The prose-scan pass also catches `t_<hex>` references in your free-form summary that don't resolve; these don't block the completion but show up as advisory warnings on the task in the dashboard.

## Block reasons that get answered fast

Bad: `"stuck"` — the human has no context.

Good: one sentence naming the specific decision you need. Leave longer context as a comment instead.

For diagnosing why a task is blocked and what to do about it, see `references/diagnosing-blocked-tasks.md` — covers review-gate, iteration budget exhaustion, token/auth, duplicates, crashes, and the full diagnosis flow.

```python
kanban_comment(
    task_id=os.environ["HERMES_KANBAN_TASK"],
    body="Full context: I have user IPs from Cloudflare headers but some users are behind NATs with thousands of peers. Keying on IP alone causes false positives.",
)
kanban_block(reason="Rate limit key choice: IP (simple, NAT-unsafe) or user_id (requires auth, skips anonymous endpoints)?")
```

The block message is what appears in the dashboard / gateway notifier. The comment is the deeper context a human reads when they open the task.

## Heartbeats worth sending

Good heartbeats name progress: `"epoch 12/50, loss 0.31"`, `"scanned 1.2M/2.4M rows"`, `"uploaded 47/120 videos"`.

Bad heartbeats: `"still working"`, empty notes, sub-second intervals. Every few minutes max; skip entirely for tasks under ~2 minutes.

## Retry scenarios

If you open the task and `kanban_show` returns `runs: [...]` with one or more closed runs, you're a retry. The prior runs' `outcome` / `summary` / `error` tell you what didn't work. Don't repeat that path. Typical retry diagnostics:

- `outcome: "timed_out"` — the previous attempt hit `max_runtime_seconds`. You may need to chunk the work or shorten it.
- `outcome: "crashed"` — the worker process died. **Do NOT jump to "reduce memory footprint" as a reflex.** Follow the full diagnostic flow in `references/diagnosing-crashes.md`: check systemd journal for OOM killer traces, check swap (`free -h`, `swapon --show`), check gateway restart timing, and only consider splitting as a last resort.
- `outcome: "spawn_failed"` + `error: "..."` — usually a profile config issue (missing credential, bad PATH). Ask the human via `kanban_block` instead of retrying blindly.
- `outcome: "reclaimed"` + `summary: "task archived..."` — operator archived the task out from under the previous run; you probably shouldn't be running at all, check status carefully.
- `outcome: "blocked"` — a previous attempt blocked; the unblock comment should be in the thread by now.

## Do NOT

- Call `delegate_task` as a substitute for `kanban_create`. `delegate_task` is for short reasoning subtasks inside YOUR run; `kanban_create` is for cross-agent handoffs that outlive one API loop.
- Modify files outside `$HERMES_KANBAN_WORKSPACE` unless the task body says to.
- Create follow-up tasks assigned to yourself — assign to the right specialist.
- Complete a task you didn't actually finish. Block it instead.
- Process a URL that was delegated to a child ticket. When a batch parent delegates individual items to children, the next worker on the parent must check comments for delegation markers (e.g., "Reel X delegated to child t_XXXX") and skip those items. Parallel parent+child processing of the same URL wastes CPU/RAM and produces duplicate work. Observed 2026-06-05: two researcher-videos workers simultaneously transcribed the same 148s Reel.
- **Use heredocs, pipe-to-interpreter, emojis, or `shell=True` in automated recovery/watchdog scripts.** The Tirith security scanner blocks these patterns with `pending_approval` — in a cron job with no interactive user, this is a silent failure. The command never executes but no error is raised. A DB repair that should have taken 1 attempt took 3 across multiple watchdog sessions (2026-06-17/18). Safe patterns: `subprocess.run()` with list args, write standalone `.py` files instead of inline scripts, plain ASCII only. Full reference: `references/tirith-safe-cron-scripts.md`.

- **Create continuation children for batch overflow.** When a worker can't finish its batch and creates an overflow child via `kanban_create`, AND the planner already created the next batch as a child of the same parent, both become `ready` simultaneously when the parent completes → parallel dispatch of CPU-heavy workers → resource saturation. Use the Memento Pattern instead: `kanban_block` with a `handoff.md` in the workspace. One task = one worker at a time. Observed 2026-06-05: t_6d953883 completed → continuation child t_d00baacc AND planner chain child t_0f11f419 both dispatched → 4 whisper processes, load 15, 420MB free RAM, 5GB swap, 7 failed transcription attempts.

### `gh issue create` quoting trap (execute_code → terminal)

When batch-creating GitHub issues from `execute_code`, shell quoting is critical. `gh issue create --title` with spaces in file paths or titles breaks because the shell splits arguments. Observed on the-swarm board 2026-05-20: 3 consecutive failures before success.

**Wrong:**
```python
path = f"/tmp/issue_{title[:20]}.txt"  # spaces in filename
write_file(path, body)
r = terminal(f"cd repo && gh issue create --title '{title}' --body-file {path} 2>&1")
# FAILS: --body-file receives "Two" "competing.txt" (split by shell)
```

**Right — use safe filenames and quote all shell arguments:**
```python
import shlex
safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', title[:40])
path = f"/tmp/issue_{safe_name}.txt"
write_file(path, body)
r = terminal(f"cd repo && gh issue create --title {shlex.quote(title)} --body-file {shlex.quote(path)} --label {shlex.quote(labels)} 2>&1")
```

Or simpler — avoid special chars entirely in temp filenames:
```python
path = f"/tmp/issue_{i}.txt"  # just use the index
r = terminal(f"cd repo && gh issue create --title '{title}' --body-file '{path}' --label '{labels}' 2>&1")
```

The key: filenames must not contain spaces. Labels and titles containing spaces are OK inside single quotes.

**Continuous tasks (monitor → report → block → repeat):** Tasks that run in cycles rather than completing once have a different termination pattern. See `references/continuous-tasks.md` for the SOUL.md requirements, common failure modes, and circuit breaker reset.

## Pitfalls

**Task stuck in `ready` — dispatcher daemon may not be running.** The Kanban dispatcher is a foreground process (`hermes kanban daemon`) on a 60-second cycle — it is NOT a systemd service by default. If no terminal session is running the daemon, tasks sit in `ready` indefinitely. Check: `ps aux | grep 'hermes kanban daemon'`. Start: `hermes kanban daemon`. Full lifecycle, symptoms, and DB lock diagnosis: `references/dispatcher-daemon-lifecycle.md`.

**Dispatcher DB corruption: `kanban.db is not a valid SQLite database`.** The dispatcher coordination DB (`/root/.hermes/kanban.db`) can get a corrupted header from an interrupted write (SIGKILL, OOM, host crash). Board DBs (`boards/<board>/kanban.db`) hold all the real data — the dispatcher DB is a coordination cache with zero critical data. Recovery: `mv kanban.db kanban.db.corrupted-backup` + restart gateway. It recreates the DB on the next dispatch tick. Board data is never at risk. Full diagnosis and recovery: `references/dispatcher-db-corruption.md`.

**WAL leak → database locked in dispatcher ticks.** Gateway logs show repeated `kanban dispatcher: tick failed on board <name>` at `kanban_db.py line 1190` (`PRAGMA journal_mode=DELETE`). The gateway process has a leaked connection holding the DB in WAL mode, blocking the DELETE transition. Recovery: `hermes gateway restart` (kills all connections). The DB itself is usually healthy — no need to move it unless restart alone doesn't fix it. If restart fixes the WAL error but tasks still don't spawn, check for **stale claim_lock** (see `references/dispatcher-daemon-lifecycle.md` — two-phase failure pattern).

**⛔ Dispatcher DB lock = silent dispatch failure (2026-06-05).** When `/root/.hermes/kanban.db` is locked, the dispatcher (which runs inside the gateway, not as a standalone daemon) silently fails every tick with `kanban dispatcher: tick failed on board <name>` at `kanban_db.py line 1190` (`PRAGMA journal_mode=DELETE`). Tasks sit in `ready` indefinitely with zero visible errors unless you check the gateway logs. The gateway itself stays up — only the dispatcher ticks fail. Diagnosis: `journalctl -u hermes-gateway --no-pager | grep "kanban dispatcher"`. Recovery: same as DB corruption — move the DB + restart gateway. Do NOT attempt to create a standalone daemon service; `hermes kanban daemon` is deprecated and exits with an error unless `--force` is used. Full lifecycle: `references/dispatcher-daemon-lifecycle.md`.

**Task state can change between dispatch and your startup.** Between when the dispatcher claimed and when your process actually booted, the task may have been blocked, reassigned, or archived. Always `kanban_show` first. If it reports `blocked` or `archived`, stop — you shouldn't be running.

**Crash-loop on `kanban_complete` — work done, kanban_complete fails.** Pattern: `hermes kanban diagnostics` shows `repeated_crashes` (480+ consecutive) with `last_error=pid N not alive`. The worker completed all work (note saved, git pushed, MinIO uploaded) but `kanban_complete` errored out. Dispatcher keeps respawning. Fix: verify work is done via `hermes kanban log <id>` (check last run output for completion indicators), then manually `hermes kanban --board <board> complete <id>`. Observed 2026-06-14 on knowledge-base board: 6 tickets crash-looped, all work already done.

**No `cancel` command — use `archive` to remove dead tasks.** The CLI has `archive` but no `cancel`. When you need to clean up duplicate/spurious/obsolete tasks (e.g. multiple identical review tasks created for the same parent), use `hermes kanban --board <board> archive <task_id>`. Archived tasks still appear in counts but are excluded from `list` by default.

**`respawn_guarded` / `active_pr` — 24h comment window blocks respawn.** The dispatcher blocks respawn when a task comment from the last 24 hours contains a GitHub PR URL (`_RESPAWN_GUARD_PR_WINDOW = 86400` in `hermes_cli/kanban_db.py`). This means: once a worker comments a PR URL (e.g. `https://github.com/Seven74AI/shop/pull/88`), the task is blocked from respawning for a full day — even after the PR is merged or closed. The guard checks task_comments, not the GitHub API.

**Claim system & liveness:** When a worker does `process wait` for heavy tasks, heartbeats stop but the claim is extended via `pid_alive` every ~15 min. The watchdog must check `last_claim_ext > last_heartbeat` before auto-blocking for "no heartbeat." Full details: `references/claim-system-and-liveness.md`. See also: `references/diagnosing-blocked-tasks.md`.

**Automated cleanup (2026-05-23):** The CI watchdog (`~/.hermes/scripts/ci-watchdog-light.py`) now deletes PR URL comments automatically when it merges a labeled PR (`kanban:TASK_ID`). Tasks going through the label-based CI pipeline are covered — no manual SQL needed. For tasks without `kanban:` labels or with review-only PR URLs (e.g. `pull/181#pullrequestreview-xxx`), manual cleanup is still required.

**Manual fix:** `DELETE FROM task_comments WHERE task_id=? AND body LIKE '%github.com%pull%'`, or avoid putting PR URLs in comments (use the PR number as text instead: `"PR #88"`). Observed on shop board 2026-05-20: 10 tasks stuck in `respawn_guarded` loop despite all PRs being closed/merged, because the PR URL comments remained within the 24h window.

**Prevent duplicate review tasks.** Before calling `kanban_create` for a review task, scan the board for an existing review of the same work. A task with a title like "Review: e2e fix checkout" in `ready`, `running`, `blocked`, or `todo` means the review already exists — link to it instead of creating a duplicate. Skipping this check causes 4× duplicate reviews (seen on music-library board 2026-05-18, 9 tasks archived).

**CRITICAL: Do NOT use `parent=` when creating reviewer tasks.** The kanban dispatcher does not promote `todo` children of blocked or running parent tasks. Creating a reviewer with `parent=coder_task_id` locks it in `todo` forever — the coder is blocked `review-required`, the reviewer never leaves `todo`, deadlock. Always create reviewers standalone (no `parent=`) and include the coder task ID in the body text instead. The block watchdog will unblock the coder when the reviewer completes. This deadlock was observed on music-library board 2026-05-18: 6 reviewer tasks stuck in `todo` until archived and recreated without parents.

**`kanban_create()` creates tasks in `todo` state, NOT `ready`.** The kanban dispatcher only picks up `ready` tasks. A reviewer task created via `kanban_create()` will sit in `todo` forever unless promoted. Workaround: after creating the reviewer task, the coder must also promote it: `terminal(f"hermes kanban --board {board} promote {review_id}")` or the block-watchdog cron must handle promotion. This was observed on 2026-05-19 across 5 boards (videogame-lab, baguette, glance, shop, the-swarm) — all review tasks created by coders were stuck in `todo`.

**⛔ `kanban_block` does NOT stop the worker process — it only prevents RE-dispatch.** The worker that called `kanban_block` keeps running: its agent loop continues, it keeps spawning subprocesses, and it keeps consuming CPU/RAM. When you block a task to stop a runaway worker, you MUST also kill the worker PID. Blocking alone leaves the worker alive indefinitely (observed 2026-06-05: a blocked researcher-videos worker spawned new whisper processes 53 minutes after the block).

**Recovery checklist when blocking a misbehaving worker:**
1. `hermes kanban --board <board> block <task_id> "reason"` — prevents RE-dispatch
2. `kill -9 <worker_pid>` — kills the current worker
3. `ps aux | grep transcribe` (or equivalent subprocess) → `kill -9` any orphans
4. `ps aux | grep "kanban task t_"` — verify no other workers for same profile

**Why subprocesses survive:** `terminal(background=true)` spawns the subprocess in its own process group via `os.setsid`. When the worker is SIGKILLed, the subprocess is reparented to init (PID 1) and keeps running. Always kill orphans after killing a worker.

**⛔ Post-credential-rotation board-wide crash loop.** When credentials are rotated (e.g., after a token compromise), ALL workers on a board may crash simultaneously if their profiles reference the old tokens. The dispatcher enters an infinite respawn cycle: `spawned=N crashed=N promoted=N auto_blocked=N` every ~60 seconds. The auto-block → promote → spawn → crash loop never self-heals because the workers die on startup (auth errors before the agent loop starts).

**Detection:** `grep "kanban dispatcher.*crashed=" gateway.log | grep -v "crashed=0"` — look for `spawned=N crashed=N` where N is identical and >0 across 3+ consecutive dispatches. Example from June 2026: 446 dispatches in 12 hours, 7 tickets looping endlessly.

**Resolution:** (1) Identify which credential is stale — compare profile `.env` tokens against the main `.env` (e.g., `grep -o 'DEEPSEEK_API_KEY=.*' /root/.hermes/.env | tail -c 5` vs the profile's `.env`). (2) Update the token(s) — copy the current key from main `.env` into the profile `.env`. (3) Reset ALL affected tickets to `ready` and zero their failure counters via SQL. **Use `status='ready'` not `status='todo'`** — the dispatcher picks up `ready` tasks immediately; `todo` tasks require promotion which the dispatcher may not handle during a crash cycle. **Include both `running` and `blocked`** in the WHERE clause — tickets in a crash loop are typically `running` (the dispatcher auto-promotes them), not `blocked`:
```sql
UPDATE tasks SET status='ready', worker_pid=NULL, current_run_id=NULL, consecutive_failures=0 WHERE board='<name>' AND status IN ('running', 'blocked');
```
(4) Kill any zombie workers that may still be running with the old credential: `pkill -f "hermes.*profile <name>"`. (5) The dispatcher picks up `ready` tasks on its next tick (~60s). Verify with `hermes kanban show <id> | grep "run "` — the latest run should show `active` and last >60s (the old-key runs all died in <61s). Do NOT rely on `hermes kanban promote` — this subcommand does not exist in all versions.

**Dispatcher race condition:** Between `kill -9` and `kanban block`, the dispatcher can respawn a new worker (observed at 11:44 on 2026-06-05: kill, then new run #119 spawned at 11:44, blocked at 11:45). This creates a brief window where a NEW worker is already running when the block lands. The block prevents further dispatches, but does not retroactively kill the just-spawned worker. Always re-verify after blocking.

**`kanban archive` also doesn't kill.** Same behavior as block — the worker keeps running. Always follow the same kill-then-verify sequence.

```python
# WRONG — creates deadlock (reviewer stuck in todo forever)
kanban_create(
    title="Review: rate limiter",
    assignee="reviewer",
    parent=os.environ["HERMES_KANBAN_TASK"],  # ← NEVER DO THIS
)

# RIGHT — standalone, references coder task in body
kanban_create(
    title="Review: rate limiter (from t_abc123)",
    assignee="reviewer",
    body="Review the rate limiter from t_abc123. Coder handoff in that task's comments.",
)

**Worker profiles have isolated $HOME — shared configs must be copied explicitly.** Each Hermes profile has its own home directory at `/root/.hermes/profiles/<name>/home/`. Files like `~/.xurl` (Twitter/X OAuth), `~/.gitconfig`, or custom tokens are NOT accessible to workers by default. When a worker blocks with "need xurl auth" or "token missing", the fix is to copy the config file from the host's home into the profile's home — not to re-authenticate. This caused edgee-lab T-WATCH to be blocked for 15+ consecutive runs with the same xurl OAuth request before the config was copied (2026-05-18). Pre-copy shared configs during team bootstrap for any profile that needs them.

**Workspace may have stale artifacts.** Especially `dir:` and `worktree` workspaces can have files from previous runs. Read the comment thread — it usually explains why you're running again and what state the workspace is in.

**Don't rely on the CLI when the guidance is available.** The `kanban_*` tools work across all terminal backends (Docker, Modal, SSH). `hermes kanban <verb>` from your terminal tool will fail in containerized backends because the CLI isn't installed there. When in doubt, use the tool.

**Overspawn: too many workers = lock contention + CPU saturation.** If the system feels slow, `hermes profile list` hangs, or you see 40+ hermes processes in `ps aux`, the autoscale may have over-cloned profiles. The root cause is usually `MAX_PROFILES_PER_ROLE` set too high. See `references/kanban-autoscale.md` for diagnosis and recovery.

**Even with moderate worker counts, CPU saturation is a distinct failure mode:** when multiple boards run CPU-intensive CI steps simultaneously (`tsc --noEmit` + `vitest`), each worker's CI can consume 100-400% CPU (tsc ~130%, vitest with 3 workers ~300% combined). On shared hosts with `max_spawn=5` and 10 active boards, this easily saturates a 4-core VM (load avg 8+ on 4 CPUs). Symptoms: workers timing out, `ps aux --sort=-%cpu` showing multiple tsc/vitest processes across different boards, `/proc/pressure/cpu some` values > 10. Mitigation: reduce `max_spawn` to match CPU cores available, or add admission control (check loadavg before spawning CI steps — see `project-ci` skill pitfalls).

**⛔ Continuation children + planner chains = parallel CPU-heavy dispatch (resource collision).** This is a specific deadlock pattern that routinely saturates shared hosts. The collision:

1. The **planner** creates a sequential chain via `parent=`: batch-1 → batch-2 → batch-3. When batch-2 completes, batch-3 is auto-promoted from `todo` to `ready`.
2. A **worker** on batch-2 can't finish all items in one session, so it creates a **continuation child** (e.g. `t_d00baacc` for the remaining 3/5 reels) via `kanban_create(... parent=batch-2)`.
3. Batch-2 completes → **both children become `ready` simultaneously** (batch-3 from the planner chain + batch-2-remainder from the worker).
4. Dispatcher sees 2 ready tasks + available spawn slots → dispatches both → 2 workers run **the same CPU-heavy workload in parallel**.

Observed 2026-06-05 on default board with researcher-videos: 3 workers spawned → 4 concurrent whisper large-v3 transcriptions → 377% CPU, load avg 11.69, 5.7GB swap used, CPU pressure 42%. Each transcription that should take ~7min was running at half speed due to CPU contention. One single-reel task (t_123f6f1b) had been running for 1+ hour.

**The fix: prefer Memento Pattern over continuation children for CPU-heavy batch work.** When you can't finish a batch in one session, do NOT create a new child task. Instead:

1. Write `handoff.md` in the workspace: completed items, remaining items, current state
2. Push to git if applicable
3. `kanban_block(reason="budget checkpoint: handoff.md in workspace — resume from item N of M")`
4. The SAME task is re-dispatched; next worker reads handoff and continues

This guarantees sequential execution (one task = one worker at a time) while preserving the planner's parent/child chain for actual batch-to-batch progression.

**Rule of thumb:** `kanban_create` = parallelizable work. If the new task must NOT run alongside the current task (CPU/RAM contention, shared state, ordering dependency), use Memento Pattern + `kanban_block` instead. Continuation children are only safe when the work is I/O-bound, stateless, or explicitly designed for parallelism.

Full diagnostic data from the 2026-06-05 incident and the OOM confirmation: `references/continuation-child-planner-chain-collision.md`.

**False-positive budget blocks from background waits.** A worker that uses `background=true` + heartbeats while waiting for a long CPU task (transcription, large build, video encode) can hit the 60-turn checkpoint despite having minimal token context (< 5K tokens). The turn counter doesn't distinguish "working turns" from "waiting turns." This is NOT the smart/dumb zone problem Matt Pocock warned about — it's a false positive of the turn-based checkpoint system. When the transcription/build finishes right after the block, just re-dispatch. See `references/smart-zone-vs-turn-budget.md`.

**Watchdog false-positives during process wait.** The crash-loop watchdog auto-blocks tasks with "no heartbeat >30min" — but `process(action="wait")` blocks the agent loop, so heartbeats CAN'T be sent. The claim system (15-min TTL, extended by the gateway via `pid_alive`) provides an independent liveness signal. The watchdog fix: check if `claim_extended > last_heartbeat` before flagging. See `references/kanban-claim-system.md` for the full mechanism.

**⛔ `process wait` blocks heartbeats but does NOT mean the worker is stuck.** When you use `process(action="wait")`, the agent loop is blocked — you physically cannot call `kanban_heartbeat()`. This is NORMAL and EXPECTED. The kernel extends your claim every ~90s via `pid_alive` — that's your real liveness signal. The watchdog checks claim extensions before auto-blocking. Do NOT avoid `process wait` out of fear of looking stuck; you will get falsely flagged if you use inline polling instead. `process wait` is the correct pattern and the system handles it.

**Project .env tokens are NOT git tokens.** Many project `.env` files contain `GITHUB_TOKEN="MOCK_GITHUB_TOKEN"` (or similar mock values) for the application's GitHub OAuth feature (`api.github.com` API calls). These are NOT the token needed for `git push`. When a task requires pushing to GitHub:
- Use the git remote URL — it should already be configured with a real token (`https://oauth2:TOKEN@github.com/...`). Run `git remote -v` to verify.
- If the remote is broken, get the real token from the main Hermes environment (not the project `.env`).
- Do NOT block with "need GITHUB_TOKEN in project .env" — the project .env token is for the app, not for git.
  See `references/detecting-placeholder-tokens.md` for the `xxd` technique to distinguish real tokens from literal placeholders in terminal output.

**GITHUB_TOKEN stripped from worker shell commands by env sanitizer.** The gateway HAS the token (verified via `systemctl show hermes-gateway | grep GITHUB_TOKEN`) and the dispatcher passes it to the worker process via `env = dict(os.environ)`. But when the worker runs shell commands via the terminal tool, `tools/environments/local.py:_sanitize_subprocess_env()` removes `GITHUB_TOKEN` because it is registered as a Copilot provider credential (`api_key_env_vars` in `hermes_cli/auth.py`). The worker process inherits the token but every shell subprocess is stripped.

**The fix (chosen over `terminal.env_passthrough` for security):** Embed the token in the git remote URL — survives the env sanitizer without leaking into every shell subprocess. Combined with the fork workflow (push to Seven74AI/repo, PR to mnlamart/repo):

```bash
TOKEN=$(grep '^GITHUB_TOKEN=' ~/.hermes/.env | head -1 | cut -d= -f2-)
git remote set-url origin "https://git:${TOKEN}@github.com/Seven74AI/REPO.git"
git remote add upstream "https://github.com/mnlamart/REPO.git"
git config --unset credential.helper  # CRITICAL: overrides URL token
```

Full diagnostic and fork CI workflow: `references/diagnosing-blocked-tasks.md` section 3. See `github-auth` skill `references/fork-ci-workflow.md` for the recipe (push → workflow_dispatch on fork → create PR).

**⛔ Token identity: the pusher on GitHub is determined by the TOKEN value, NOT the `git` username in the URL.** The pattern `https://git:$TOKEN@github.com/...` means GitHub identifies the pusher by the TOKEN itself. If `GITHUB_TOKEN` in `~/.hermes/.env` is ever temporarily set to a different account's token (accidental copy-paste, credential testing, rotation mistake), ALL pushes from kanban workspaces will show that account as the pusher — while the commit author (`git config user.name`) still says "Hermes Agent". The commit looks legitimate (right author, right repo) but the pusher is wrong. **There is no audit trail for .env changes** — the file is not under version control. If you discover a rogue pusher on a commit:

1. Search for the commit hash in coder sessions: `grep -rl "<sha>" /root/.hermes/profiles/coder/sessions/`
2. Extract the token-source command from the session (usually message ~13: `grep '^GITHUB_TOKEN=' /root/.hermes/.env`)
3. Compare tokens across `.env`, `gh auth token`, and `~/.git-credentials` (they can differ!)
4. Check `.env` modification time (`stat ~/.hermes/.env`) — if it's after the commit, the token may have been changed since

Prevention: periodically verify `gh auth status` matches the expected account. See `references/tracing-git-token-identity.md` for the full forensic recipe.

**Never run long test suites inside the agent loop.** Running `npx playwright test`, `npm run test:e2e`, or benchmark scripts inside the agent loop burns your iteration budget (90 max) because every test log line, assertion, and wait consumes an iteration. When your task involves running test suites or benchmarks:
- Use `terminal(background=true, notify_on_complete=true, timeout=600)` to run the test/benchmark as a background process.
- The script runs independently and notifies you when it's done — you only spend ~3-4 iterations total (launch + analyze results).
- For benchmarks: the project likely has a `scripts/benchmark.sh` that handles build → server start → tests → stop → JSON report. Call it in background.
- For single test files: start the dev server in background first, then run `npx playwright test <file>` in background with notify_on_complete.
- Do NOT run `npm run test:e2e` or `npx playwright test` directly in the agent loop. This is the #1 cause of iteration budget exhaustion on testing tasks.

**After launching a background process, use `process(action="wait")` — never poll.** Polling loops (`sleep 10 && tail logfile` repeated every turn) burn one iteration per cycle. A 15-minute benchmark consumes 90 iterations of polling — exactly exhausting the budget. Instead:
- Launch: `terminal("script.sh", background=true, notify_on_complete=true)`
- Wait: `process(action="wait", timeout=3600)` — blocks without consuming ANY iterations
- Then read results with `read_file` or `search_files`

This is the #2 cause of budget exhaustion: the worker launches correctly in background, then burns its budget waiting. One `process wait` call replaces 50-100 polling iterations.

**Profile config changes require re-dispatch.** When you change a profile's `config.yaml` (e.g., increasing `max_turns` from 90 to 360), the change only applies to NEW spawns. A worker already running has the old config loaded at startup. The task must be unblocked and re-dispatched for the new config to take effect. Check with `hermes kanban show <id> | grep "run "` — if the run started before the config change, it has the old limits.

**When background instructions fail — the self-contained script fallback.** Workers sometimes ignore task-body instructions to use background mode, repeatedly burning their budget on inline test runs. When this happens and a task hits 3+ budget-exhaustion retries, do NOT just update the task body again. Instead, create a single shell script that does ALL the heavy work (benchmark, tweak, re-benchmark, report) and update the task body to say: "Run this ONE command in background, then wait. That's it." The script does the multi-step loop internally; the worker only calls it once. This eliminates the worker's opportunity to iterate. See `references/e2e-loop-script-pattern.md` for the explanation and `templates/e2e-iteration-loop.sh` for a starter script.

**⛔ `kanban_block` does NOT kill the worker process — blocked workers keep spawning orphans.** The DB transition (running → blocked) prevents RE-dispatch but the existing process keeps running until it hits turn budget, crashes, or is killed externally. A blocked worker can continue spawning subprocesses (transcriptions, builds) for 50+ minutes after the block. Observed 2026-06-05: t_0f11f419 blocked at 11:45, worker spawned a new whisper process at 12:38 — 53 minutes later. The block→archive pattern also has a race: the dispatcher can respawn a worker between the `kill -9` and the `archive` command.

  **Prevention:** After blocking/archiving a task, SIGKILL the worker PID to stop orphan work:
  ```bash
  hermes kanban --board <board> block <id> "reason"
  kill -9 $(hermes kanban --board <board> show <id> --json | jq -r '.worker_pid')
  ```
  Then kill any orphan transcription/build processes: `ps aux | grep transcribe | grep -v grep | awk '{print $2}' | xargs kill -9`.

**Dispatcher TERMINAL_TIMEOUT override:** When spawning workers, `_default_spawn` calls `_worker_terminal_timeout_env(task.max_runtime_seconds, ...)` (kanban_db.py:5516). If `max_runtime_seconds` is set, TERMINAL_TIMEOUT is overridden to `max(1, runtime - 30)`. If not set, the gateway's env TERMINAL_TIMEOUT is inherited (or the code default of 180s). This means `process(action="wait")` can time out at 180s even when the worker passes `timeout=3600` — the env var caps all process waits.

**OOM is the #1 killer of CPU/RAM-heavy background processes, not SIGTERM from the agent loop.** Thorough investigation 2026-06-05 (traced every kill path in the codebase: claim expiry, max_runtime, crashed detection, TERMINAL_LIFETIME, process_registry.wait, agent.close, interrupt mechanism, step_callback, gateway agent cache eviction, kanban_heartbeat side effects, cgroup limits) found NO code path that kills background processes during normal kanban worker operation. Background processes tested successfully: 8-min sleep loop, 2GB+CPU stress test, and actual large-v3 transcription (19 min). All completed cleanly. The earlier "SIGTERM" reports were actually foreground timeouts (exit 124) and OOM SIGKILLs (exit -9) from parallel whisper processes. With a single worker, background mode works perfectly. Always check `free -h` and `ps aux | grep transcribe` before assuming a kill is internal — it's almost always resource exhaustion.

**⛔ `process wait` blocks heartbeats — this is NORMAL, not a bug.** When you call `process(action="wait")`, the agent loop is blocked — you physically cannot call `kanban_heartbeat()` during the wait. This does NOT mean you're stuck. The kernel extends your claim every ~15 min via `claim_extended` events with `reason=pid_alive` — that's your real liveness signal. The watchdog checks for recent claim extensions before auto-blocking. Do NOT avoid `process wait` out of fear of looking stuck; use inline polling instead and you'll burn your turn budget. `process wait` is the correct pattern. Full claim system details: `references/claim-system.md`.

**Disk saturation from scratch workspaces.** Each `scratch` workspace clones the full project repo (including node_modules). At 1.5–2.7 GB per workspace, 25 completed tasks can consume 40+ GB.
- An automated GC cron job (`eb1ab33f9bf4`, every 15m) uses `~/.hermes/scripts/kanban-gc-workspaces.py` to delete workspaces of done/archived tasks older than 5 minutes.
- The 5-minute delay prevents deleting a workspace mid-recovery. If a task is done/archived, no re-dispatch happens — so 5 minutes is safe.
- If this cron job is ever missing, recreate it: `hermes cron create --name "kanban workspace GC" --schedule "every 15m" --script kanban-gc-workspaces.py --no-agent --deliver local`
- When diagnosing disk pressure: `du -sh /root/.hermes/kanban/boards/*/workspaces/` then `df -h /`.
- For bulk manual cleanup during emergencies, see `references/workspace-disk-cleanup.md`.

**`hermes kanban list --status` takes only ONE value, not comma-separated.** Passing `--status ready,running,blocked` fails with `invalid choice`. The workaround: use `--json` and filter in Python.

```bash
# ❌ FAILS
hermes kanban --board shop list --status ready,running,blocked

# ✅ Workaround — single status per call, or filter --json
hermes kanban --board shop list --json | python3 -c "
import sys, json
tasks = json.load(sys.stdin)
for t in tasks:
    if t.get('status') not in ('done','archived'):
        print(f\"{t['status']:10s} {t['id'][:12]}  {t['title'][:90]}\")
"

# For scanning ALL boards at once
for board in $(ls /root/.hermes/kanban/boards/); do
  hermes kanban --board "$board" list --json | python3 -c "
import sys, json
tasks = json.load(sys.stdin)
active = [t for t in tasks if t.get('status') not in ('done','archived')]
if active:
    print(f'=== $board ({len(active)} active) ===')
    for t in active:
        print(f\"  {t['status']:10s} {t['id'][:12]}  {t.get('assignee',''):20s} {t['title'][:90]}\")
" 2>/dev/null
done
```

This pattern also avoids one `hermes kanban list` call per status value, saving turn budget.

## CLI fallback (for scripting)

Every tool has a CLI equivalent for human operators and scripts:
- `kanban_show` ↔ `hermes kanban show <id> --json`
- `kanban_complete` ↔ `hermes kanban complete <id> --summary "..." --metadata '{...}'`
- `kanban_block` ↔ `hermes kanban block <id> "reason"`
- `kanban_create` ↔ `hermes kanban create "title" --assignee <profile> [--parent <id>]`
- etc.

Use the tools from inside an agent; the CLI exists for the human at the terminal.

**`kanban edit` only supports `--result`/`--summary`/`--metadata` — no `--body`.** The original body (from `kanban_create --body`) is immutable via the CLI.

For batch-ticket body corrections where a worker must skip already-processed items, a **comment alone is NOT sufficient** — workers read the body as their primary instruction and routinely re-process completed items even when a comment marks them done (observed 2026-06-05: DVzAWsEko0Q transcribed 3 times across 2 worker runs because the body still listed all 5 URLs unmarked). Instead, update the body directly via sqlite3:

```python
import sqlite3
db = sqlite3.connect("/root/.hermes/kanban.db")  # default board — NOT kanban/kanban.db
db.execute("UPDATE tasks SET body = ? WHERE id = ?", (new_body, task_id))
db.commit()
```

**DB path for default board:** ``/root/.hermes/kanban.db`` (at hermes root), NOT ``/root/.hermes/kanban/kanban.db``. Per-board DBs live at ``/root/.hermes/kanban/boards/<slug>/kanban.db``. The root-level ``kanban/kanban.db`` is a coordination cache with 0 tables — never edit it.

After updating the body, also reset `status` to `ready` and clear `worker_pid` + `current_run_id` so the dispatcher picks it up fresh:

```python
db.execute("UPDATE tasks SET status='ready', worker_pid=NULL, current_run_id=NULL, consecutive_failures=0 WHERE id=?", (task_id,))
```

Then kill any orphaned worker processes: `pkill -f "kanban.*<task_id>"`.

For non-batch corrections where a comment is sufficient, use `hermes kanban comment` — it's simpler and audit-trailed.
