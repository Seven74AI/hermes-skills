# Dependency Update Pipeline — Kanban Decomposition Pattern

Concrete example: decomposing a full npm dependency update (38 outdated packages, major version jumps) into a phased Kanban task graph.

## When to use this pattern

- Project has 20+ outdated dependencies including major version jumps
- Multiple specialist profiles exist (researcher, coder, reviewer) for the project
- Want autonomous phased execution with validation gates between phases
- No renovate PRs exist (stale/forked repo) — use `npm-check-updates` approach

## Task graph

```
T1 (researcher) ─────────────────────────────────────┐
        Analyze migration risks                       │
        (Express 5, Prisma 7, Vitest 4,               │
         Vite 8, TS6, Zod 4, RR7...)                  │
                                                      │
T2 (coder) ──→ T3 (coder) ──→ T4 (coder) ──→ T5 (coder)
  Phase 1       Phase 2        Phase 3        Phase 4
  minors/       likely-safe    risky          Express 5
  patches       majors         majors         + rate-limit
                                                      │
                                      ┌───────────────┘
                                      ↓
                              T6 (reviewer)
                              Verification finale
                              vitest+tsc+lint+e2e+build
```

## Tenant setup

Use `--tenant <project-name>` on every `kanban_create` call. This isolates tasks per project in a single physical Kanban DB.

```bash
hermes kanban create "..." --assignee music-coder --tenant music-library
```

## Profile naming convention

For multi-project setups, prefix profiles with the project name:
- `music-planner`, `music-coder`, `music-researcher`, `music-reviewer`
- `shop-planner`, `shop-coder`, `shop-researcher`, `shop-reviewer`

Discover available profiles before creating tasks: `hermes profile list`

## Phase details

### T1 — Research (parallel with T2)
Assign to researcher profile. Analyze codebase for patterns that will break with major upgrades:
- Express 5: `grep -rn "app\.\(get\|all\|use\)('\*'" server/`
- Prisma 7: check for `prisma.config.ts`, adapter usage, typedSql
- Vitest 4: check for `node:*` imports in test files
- TS6/Zod4/RR7: identify type-heavy files

### T2 — Phase 1: batch minors/patches
`npx npm-check-updates -t minor -u` → install → prisma generate → test
Almost always passes. Commit: `chore: batch minor/patch npm updates`

### T3 — Phase 2: likely-safe majors
Packages that rarely break: dotenv, cross-env, glob, get-port, execa, fs-extra, isbot, close-with-grace, lru-cache, mime-types, morgan, set-cookie-parser, compression, cookie, adm-zip, music-metadata, openimg, sharp, ws
`npx npm-check-updates -f '<list>' -u` → install → test → commit

### T4 — Phase 3: risky majors (HEAVIEST — can be split)

**Monolithic approach** (single coder):
react-router, vite, vitest, typescript, zod, tailwindcss, tailwind-merge, @vitejs/plugin-react, tw-animate-css, prettier, prettier-plugin-tailwindcss, esbuild, remix-utils, tsx, @vitest/coverage-v8, eslint, jsdom, googleapis, msw, prettier-plugin-sql, esbuild-plugin-tsconfig-paths, bcryptjs, better-sqlite3

Fix order:
1. Vitest 4 → externalizeNodeBuiltins plugin
2. TS6 → type errors
3. Vite 8 → config adapt
4. Zod 4 → schemas
5. Tailwind 4 → classes
6. eslint 10 → config

If tests fail after full batch, bisect by reverting half the packages.

**Split-and-merge approach** (3+ coders, ~1.5x speedup):
Replace the monolithic T4 with a base + parallel workers + merge structure:

```
T4-base (coder)        Apply ALL risky majors ncu+install, commit to branch
   │
   ├── T4-config (coder)       Fix ONLY vite.config.ts (externalizeNodeBuiltins, Vite 8)
   │                            Branch: fix/vitest-vite-config, merge back when done
   │
   └── T4-code (coder-2)⚡      Fix TS6+RR7+Zod4+Tailwind4+eslint (everything else)
                                Branch: fix/ts6-rr7-zod4-tailwind4, merge back when done
   │
   ↓
T4-merge (coder)        Merge both branches, resolve conflicts, run full test suite
```

Steps:
1. Archive the old monolithic T4: `hermes kanban archive <old_t4_id>`
2. Create T4-base (depends on T3): apply ncu, npm install, `git checkout -b batch/risky-majors-base`, commit
3. Create T4-config ⚡ T4-code (both depend on T4-base, different profiles → parallel)
4. Create T4-merge (depends on T4-config + T4-code): merge, test
5. Fix downstream links: `hermes kanban unlink <old_t4> <t5>` then `hermes kanban link <t4_merge> <t5>`

Profile requirements: at least 2 coder profiles (e.g., `music-coder` + `music-coder-2`). Create extras with `hermes profile create <name>-2 --clone-from <name>`.

Critical: link new parent BEFORE unlinking old one. Unlinking from an archived parent promotes the child to `ready` immediately — the dispatcher will claim it before you can link the replacement. See `kanban-orchestrator` pitfalls.

### T5 — Phase 4: known-breaking
`npx npm-check-updates -f 'express,express-rate-limit' -u`

Express 5 wildcards: `'*'` → `'{*path}'` everywhere
Rate-limit v8: `import rateLimit, { ipKeyGenerator } from 'express-rate-limit'`

### T6 — Verification (gated on T4+T5)
Full suite: vitest run → tsc --noEmit → lint → build → e2e
If failures remain → create fix task for coder with parent T6

## Key commands reference

```bash
# Discover profiles
hermes profile list

# Create task with tenant
hermes kanban create "title" --assignee <profile> --tenant <project> [--parent <id>]

# View board
hermes kanban list --tenant <project>

# Verify gateway running
hermes gateway status

# Create task with dependency (child waits for parent)
hermes kanban create "title" --assignee <profile> --tenant <project> --parent <parent_id>

# Clone profile for scaling
hermes profile create <name>-2 --clone-from <name>

# Reassign task to different profile (--reclaim resets claim)
hermes kanban reassign <task_id> <new_profile> --reclaim

# Fix parent links (POSITIONAL args, not --parent/--child flags)
hermes kanban link <parent_id> <child_id>
hermes kanban unlink <parent_id> <child_id>

# Stop a runaway task
hermes kanban reclaim <task_id>

# Archive obsolete task
hermes kanban archive <task_id>
```

## Documentation update pipeline (post-deps)

After the dependency phases complete, a separate doc update pipeline fans out in parallel:

```
T6 (verification) ──→ T7  (research)    README.md
                  ├── T8  (research-2)⚡ ARCHITECTURE.md
                  ├── T9  (research-3)⚡ PRISMA migration guide
                  ├── T10 (research-2)⚡ mocking.md
                  └── T11 (research-3)⚡ TESTING_PLAN.md
                          │
                          ↓
                    T12 (reviewer)       Revue finale de cohérence
```

T7-T11 are independent (no parent links between them) → when spread across 2 profiles (hard cap), they run 2x faster than serial. T12 gates on all of them.

Profile cloning for doc parallelism:
```bash
hermes profile create music-researcher-2 --clone-from music-researcher
hermes profile create music-researcher-3 --clone-from music-researcher
hermes kanban reassign <t8_id> music-researcher-2 --reclaim
hermes kanban reassign <t9_id> music-researcher-3 --reclaim
# ... etc
```

## Pitfalls

- **Don't create all tasks as independent ready cards.** Use `--parent` so phases don't run out of order.
- **Always pass `--tenant`** on every kanban_create or tasks go to wrong namespace.
- **T4 is the bottleneck.** Expect 30-45 min and possible bisecting. The Vitest 4 + TS6 + Vite 8 combo frequently needs iteration. Split into parallel sub-tasks (see above) for ~1.5x speedup.
- **Don't forget `prisma generate --sql`** after every `npm install`.
- **Mandatory triple-check:** vitest run + tsc --noEmit + lint. Vitest alone misses type errors.
- **Unlinking from archived parent → immediate dispatch.** When a parent is archived, unlinking the child promotes it to `ready` instantly. The dispatcher will claim it before you can link a replacement. Always: 1) `hermes kanban link <new_parent> <child>` FIRST, then 2) `hermes kanban unlink <old_parent> <child>`. If it already ran away, `hermes kanban reclaim <child>` to reset.
- **`hermes kanban link/unlink` use positional args:** `hermes kanban link <parent_id> <child_id>`, NOT `--parent <id> --child <id>`. Using flags silently fails with a cryptic error.
- **`hermes kanban reassign` needs `--reclaim`** to reset the claim from the current profile. Without it, the task stays stuck on the old profile's queue.
