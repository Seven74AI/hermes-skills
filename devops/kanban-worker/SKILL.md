---
name: kanban-worker
description: Pitfalls, examples, and edge cases for Hermes Kanban workers. The lifecycle itself is auto-injected into every worker's system prompt as KANBAN_GUIDANCE (from agent/prompt_builder.py); this skill is what you load when you want deeper detail on specific scenarios.
version: 2.0.0
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

**Continuous tasks (monitor → report → block → repeat):** Tasks that run in cycles rather than completing once have a different termination pattern. See `references/continuous-tasks.md` for the SOUL.md requirements, common failure modes, and circuit breaker reset.

## Pitfalls

**Task state can change between dispatch and your startup.** Between when the dispatcher claimed and when your process actually booted, the task may have been blocked, reassigned, or archived. Always `kanban_show` first. If it reports `blocked` or `archived`, stop — you shouldn't be running.

**No `cancel` command — use `archive` to remove dead tasks.** The CLI has `archive` but no `cancel`. When you need to clean up duplicate/spurious/obsolete tasks (e.g. multiple identical review tasks created for the same parent), use `hermes kanban --board <board> archive <task_id>`. Archived tasks still appear in counts but are excluded from `list` by default.

**Prevent duplicate review tasks.** Before calling `kanban_create` for a review task, scan the board for an existing review of the same work. A task with a title like "Review: e2e fix checkout" in `ready`, `running`, `blocked`, or `todo` means the review already exists — link to it instead of creating a duplicate. Skipping this check causes 4× duplicate reviews (seen on music-library board 2026-05-18, 9 tasks archived).

**CRITICAL: Do NOT use `parent=` when creating reviewer tasks.** The kanban dispatcher does not promote `todo` children of blocked or running parent tasks. Creating a reviewer with `parent=coder_task_id` locks it in `todo` forever — the coder is blocked `review-required`, the reviewer never leaves `todo`, deadlock. Always create reviewers standalone (no `parent=`) and include the coder task ID in the body text instead. The block watchdog will unblock the coder when the reviewer completes. This deadlock was observed on music-library board 2026-05-18: 6 reviewer tasks stuck in `todo` until archived and recreated without parents.

**`kanban_create()` creates tasks in `todo` state, NOT `ready`.** The kanban dispatcher only picks up `ready` tasks. A reviewer task created via `kanban_create()` will sit in `todo` forever unless promoted. Workaround: after creating the reviewer task, the coder must also promote it: `terminal(f"hermes kanban --board {board} promote {review_id}")` or the block-watchdog cron must handle promotion. This was observed on 2026-05-19 across 5 boards (videogame-lab, baguette, glance, shop, the-swarm) — all review tasks created by coders were stuck in `todo`.

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

**Disk saturation from scratch workspaces.** Each `scratch` workspace clones the full project repo (including node_modules). At 1.5–2.7 GB per workspace, 25 completed tasks can consume 40+ GB. When the disk fills, kanban DB operations fail with "disk I/O error" and the gateway cannot function. Prevention:
- An automated GC cron job (`eb1ab33f9bf4`, every 15m) uses `~/.hermes/scripts/kanban-gc-workspaces.py` to delete workspaces of done/archived tasks older than 5 minutes.
- The 5-minute delay prevents deleting a workspace mid-recovery. If a task is done/archived, no re-dispatch happens — so 5 minutes is safe.
- If this cron job is ever missing, recreate it: `hermes cron create --name "kanban workspace GC" --schedule "every 15m" --script kanban-gc-workspaces.py --no-agent --deliver local`
- When diagnosing disk pressure: `du -sh /root/.hermes/kanban/boards/*/workspaces/` then `df -h /`.
- For bulk manual cleanup during emergencies, see `references/workspace-disk-cleanup.md`.

## CLI fallback (for scripting)

Every tool has a CLI equivalent for human operators and scripts:
- `kanban_show` ↔ `hermes kanban show <id> --json`
- `kanban_complete` ↔ `hermes kanban complete <id> --summary "..." --metadata '{...}'`
- `kanban_block` ↔ `hermes kanban block <id> "reason"`
- `kanban_create` ↔ `hermes kanban create "title" --assignee <profile> [--parent <id>]`
- etc.

Use the tools from inside an agent; the CLI exists for the human at the terminal.
