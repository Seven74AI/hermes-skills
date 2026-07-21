---
name: project-ci
description: "Standard CI workflow for all projects — full validation after dependency changes."
version: 1.0.0
metadata:
  hermes:
    tags: [ci, testing, workflow]
---

# Project CI — Standard Workflow

CI commands to run after any dependency change (`npm install`, `pnpm install`, etc.).

## Full CI Command

```bash
vitest run && tsc --noEmit && npm run lint && playwright test --workers=1
```

For diagnosing and fixing flaky E2E tests (SQLite contention, networkidle hangs, timeout defaults, a11y color-contrast, CDP timing, mock fixture prerequisites), see `references/flaky-e2e-fixes.md` and `references/e2e-mock-fixtures.md` — recurring patterns observed across shop, the-swarm, and music-library projects.

## Runtime Upgrades

When upgrading Node.js itself (e.g. 22→24), not just npm packages, the surface area spans package.json, Dockerfile, CI config, and lockfiles — with a lockfile staleness pitfall. See `references/node-runtime-upgrade.md` for the full checklist and verification steps.

## Why All Four

- **`vitest run`** — unit + integration tests (misses: type errors, ESLint, e2e)
- **`tsc --noEmit`** — TypeScript type checking (catches type errors vitest ignores)
- **`npm run lint`** — ESLint (catches style/pattern issues)
- **`playwright test --workers=1`** — E2E tests (serial mode avoids race conditions)

## Pitfalls

- Running only `vitest` is NOT enough — it won't catch TS/ESLint/e2e failures
- `playwright test` without `--workers=1` can have race conditions in CI
- **⛔ Workflow `name` MUST be `CI` — exact match.** The branch protection rule `contexts: ["CI"]` requires a check literally named `CI`. If the workflow is named `🚀 Deploy` (or anything else), `gh pr merge` fails even when every job is green. This causes a CI watchdog infinite loop: merge fails → unblock → coder respawns → re-blocks → merge fails again. Real case (shop + music-library 2026-05-20): both repos had `name: 🚀 Deploy` instead of `name: CI`. Fixed by renaming workflow.
- Always run the full pipeline after `npm install`/dependency updates
- **CPU load awareness on shared systems:** `tsc --noEmit` and `vitest` are CPU-bound (each can consume 100-130% of a core). On shared hosts running multiple kanban boards, simultaneous CI across boards saturates all cores (e.g., 3 boards × CI = load avg 8+ on a 4-core VM, causing thrashing and worker timeouts). Before running CI steps, check system load: if `loadavg 1m > nproc * 0.75`, either wait for a slot or run with reduced parallelism (`vitest --pool=forks --poolOptions.forks.singleFork`, avoid starting a second `tsc` while one is already running). The pattern to check: `uptime`, `/proc/loadavg`, `ps aux --sort=-%cpu | head -10` — if multiple boards are already running tsc/vitest, delay your CI run. See `systematic-debugging` skill `references/cpu-pressure-diagnostics.md` for full diagnostic workflow.
- **pnpm v10+: `onlyBuiltDependencies` overrides `allowBuilds`.** In pnpm v10+, `pnpm.onlyBuiltDependencies` in `package.json` takes precedence over `allowBuilds` in `pnpm-workspace.yaml`. If a native package is in `allowBuilds` but NOT in `onlyBuiltDependencies`, pnpm silently skips its build scripts — the native module never compiles. Symptom: `Could not locate the bindings file`. Fix: ensure every native package is listed in BOTH places, or use only `onlyBuiltDependencies` (the authoritative source for pnpm v10+). See shop skill for the concrete `better-sqlite3` example.
- **pnpm v11: `onlyBuiltDependencies` silently ignored.** `pnpm.onlyBuiltDependencies` in `package.json` is NOT honored in pnpm v11.1.2. Only `pnpm-workspace.yaml` with the `allowBuilds` **map** format works. Without this, native packages (better-sqlite3, esbuild, prisma, sharp, etc.) fail with `ERR_PNPM_IGNORED_BUILDS` in CI. Full details in `references/github-actions-pnpm-workflow.md` Step 5.
  - **Version-specific summary:** v10 → `onlyBuiltDependencies` is authoritative (ignores `allowBuilds`). v11 → `allowBuilds` is authoritative (ignores `onlyBuiltDependencies`). Keep both configs in sync to be safe across versions.
- **pnpm ESLint bin pitfall:** Under pnpm, `node_modules/.bin/eslint` is a Unix shell script, not a JS file. Never use `node ./node_modules/.bin/eslint` — use `eslint` directly (pnpm resolves shell scripts correctly).
- **`packageManager` must be exact version.** `"packageManager": "pnpm@10"` is invalid and causes `WARN Cannot switch to pnpm@10: "10" is not a valid exact version` on every pnpm command. Fix: pin to `"pnpm@10.9.0"` (or whatever version the lockfile was generated with). CI workflows using `pnpm/action-setup@v6` with `version: 10` work fine regardless, but the warning spam is noise.
- **`|| true` in CI typecheck step silently swallows errors.** `pnpm typecheck || true` makes the step always exit 0 regardless of `tsc --noEmit` errors. CI appears green while TypeScript has compilation errors. This is the #1 CI regression risk — consolidation PRs that touch workflow files can re-introduce `|| true` after it was previously removed. Real case (shop 2026-05-20): commit 15f1d1e removed `|| true`, then consolidation commit 0774571 re-introduced it. Always grep for `|| true` in workflow files after any consolidation or CI change.
- **`gh` CLI defaults to upstream repo on forks.** `gh pr list`, `gh pr view`, `gh run view` query the repo's default remote — on forks, this is often the upstream (`upstream/owner`), not your fork. If you see empty results for a PR you know exists, the CLI is querying the wrong repo. Always use `--repo Owner/fork` explicitly. Example: `gh pr list --repo Seven74AI/music-library`. Same applies to `gh run view --repo`. This caused a 10-minute debugging dead-end in the music-library project.\n- **Prisma v7: `prisma.config.ts` overrides `package.json` seed config.** When a `prisma.config.ts` exists, Prisma CLI ignores `"prisma": { "seed": "..." }` in `package.json`. The seed must be configured in the config file's `migrations.seed` field. Symptom: `prisma db seed` says "No seed command configured" despite package.json having it. Full details in shop skill.

## Test Infrastructure — All Projects Must Have It

The user's directive: **every project that produces software must have unit + E2E tests.** If a board exists and has code, it needs a test ticket in its backlog. The standard is:

| Stack | Unit tests | E2E tests | CI |
|-------|-----------|-----------|---|
| **Node/TS/React** | Vitest | Playwright (--workers=1) | `vitest run && tsc --noEmit && lint && playwright test --workers=1` |
| **Python** | pytest | playwright (or skip if CLI-only) | pytest in GitHub Actions |
| **Godot/GDScript** | GUT (headless) | Manual playtest OR GUT integration | `godot --headless --quit --path .` in CI |
| **Swift/macOS** | XCTest | Manual + XCTest UI | xcodebuild in CI |
| **Chrome Extension** | Jest (or Vitest) | Playwright (load extension, navigate) | Jest + Playwright in CI |

**When to add test tickets:**
- New project → test ticket in the first 3 phases
- Existing project with no tests → immediate test ticket
- Project with tests but unknown coverage → coverage audit ticket
- After any major feature → ensure tests cover it

**Test ticket template:**
```
TEST: <stack> — <scope>. Cible: >85% coverage. CI verte obligatoire.
```

**Coverage targets:**
- Game prototypes (baguette, videogame-lab): >80% (headless GUT)
- Production web apps (music-library, shop): >85% (Vitest + Playwright)
- Extensions (MIROIR): >80% (Jest/Vitest + Playwright E2E)
- macOS apps (glance): >70% (XCTest, no E2E possible headless)

**Audit approach:** If a project already has tests but coverage is unknown, create an audit ticket first — don't assume coverage is good just because CI is green. CI passing ≠ good coverage.

## E2E Test Diagnosis — Playwright/CI Flaky Test Root Cause

When an E2E test fails intermittently, do NOT reach for `waitForTimeout` or `waitForURL` as a first response. Use the diagnostic flow below. For recurring flaky patterns (networkidle hangs, SQLite contention, CDP timing, a11y color-contrast, shadcn checkbox hydration, toast races), see `references/flaky-e2e-fixes.md`.

### Phase 0 — Run locally first. Never push guessed fixes.

CI is for verification, not primary testing. Run the failing test locally before pushing. If you can't, figure out why (missing env vars, build step, wrong command) and fix that first. 

Never assume the bug. Read the actual error output: check `error-context.md` for the page snapshot, check CI logs (not just the summary), run the test yourself.

### The Two-Environment Problem (SESSION_SECRET trap)

Playwright E2E tests run with TWO separate process environments that must be in sync:

1. **Test process** — `process.env` at the top of `playwright.config.ts`. Runs fixtures like `login()`.
2. **webServer subprocess** — `webServer.env` in `defineConfig()`. Runs the app server.

If `SESSION_SECRET` differs between them, the cookie created by `login()` is rejected by the server, and the user appears logged out silently. The page snapshot shows "Welcome back!" login form instead of authenticated content.

**Fix:** Set every env var required by `env.server.ts` (or equivalent) in BOTH locations with the SAME value. Common required vars: `DATABASE_URL`, `DATABASE_PATH`, `CACHE_DATABASE_PATH`, `INTERNAL_COMMAND_TOKEN`, `HONEYPOT_SECRET`, `SESSION_SECRET`.

### Diagnosis Flow

1. **Read `error-context.md`** first — `test-results/<test>-retryN/error-context.md`. The `# Page snapshot` tells you exactly what rendered:
   - `Internal Server Error` → server crashed. Check env vars and stderr.
   - Login screen ("Welcome back!") → `login()` fixture failed. SESSION_SECRET mismatch.
   - Vite `virtual:react-router/server-build` → `NODE_ENV` mismatch. Server used Vite dev mode.
   - Expected page but missing element → element genuinely absent. Check component code.

2. **Run the server manually** to find missing env vars:
   ```bash
   npm run start:mocks > /tmp/stdout.log 2> /tmp/stderr.log &
   sleep 10
   curl -s http://localhost:3000/some-page
   cat /tmp/stderr.log | grep "Invalid environment variables" -A 10
   ```

3. **Check env.server.ts** for vars that become required with `NODE_ENV=production`.

### Additional Pitfalls

- **`CI: true` must be set in workflow `env:` blocks.** Without it, Playwright webServer falls back to `npm run dev` (slower, debug port conflicts).
- **`@slow` tag does NOT extend timeout.** Use `test.setTimeout(30000)` explicitly.
- **`cross-env` in npm scripts overrides `webServer.env` values.** If `start:mocks` uses `cross-env NODE_ENV=production`, it will override whatever you set in `webServer.env`.
- **`waitForTimeout` / pre-created `waitForURL` are anti-patterns.** They mask timing issues. Find the real synchronization gap.

Full diagnostic walkthrough: `references/playwright-env-vars.md`.

## Pre-Push Hooks — Local Quality Gate

Pre-push hooks catch failures BEFORE they reach CI/GitHub. Every repo MUST have a `.githooks/pre-push` script that runs the appropriate fast-path tests. This is the first line of defense — CI runs later on push, but pre-push saves round-trips.

**Per-stack hook template:**

| Stack | Pre-push command | Notes |
|-------|-----------------|-------|
| **Node/TS** | `vitest run && tsc --noEmit` | Via husky or `.githooks/pre-push`. Skip Playwright E2E (too slow for pre-push). |
| **Python** | `pytest` | Skip slow integration tests if marked. |
| **Godot** | `godot --headless --quit --path .` | Skip gracefully with warning if Godot not installed. |
| **Swift** | `swift test` or `xcodebuild test -scheme X -destination 'platform=macOS'` | Skip if no Package.swift. |
| **HTML/static** | `npm run lint` or skip | No tests to run. |

**Hook setup (per repo):**
```bash
mkdir -p .githooks
# Create .githooks/pre-push with appropriate test command
git config core.hooksPath .githooks
```

**Fast-path optimization:**
The hook should inspect which files changed and skip irrelevant tests:
- Only `.md`/`.txt` changed → skip all tests
- Only `.ts`/`.tsx` changed → run `tsc --noEmit`, skip vitest if no source logic changed
- Godot scenes/assets changed → run headless validation
- Full source changes → run full pre-push suite

**Coder workers** push code after running the full test suite in background (see `kanban-profile-blueprint` SOUL.md). The pre-push hook provides a second safety net on the git level.

**Bypass in emergencies:** `git push --no-verify` (should be documented in each repo's CONTRIBUTING.md).

### Shell hook `&&` pitfall

Commands on separate lines in shell hooks (`.husky/pre-commit`, `.githooks/pre-push`) run **independently** — the script continues past failures. Without `&&` chaining, only the **last** command's exit code determines success/failure. A `tsc --noEmit` with 195 errors on line 3 is invisible if `vitest --run` on line 4 exits 0. Even worse: tsc exits 2, vitest exits 1 for "no test files" — a *different* failure masks the real one, making the agent think the hook works.

```bash
# BROKEN — failures don't cascade. Each line executes independently.
npx lint-staged
npm run lint
npm run typecheck
npm run test -- --run

# CORRECT — any failure aborts the hook immediately.
npx lint-staged &&
npm run lint &&
npm run typecheck &&
npm run test -- --run
```

**Real case (music-library 2026-07-20):** hook had no `&&`, tsc had 195 pre-existing errors (exit 2), but `npm run test -- --run` exited 1 (no test files found) — a different failure masked the tsc error. Agent bypassed the hook with `--no-verify` thinking typecheck was clean, pushed a commit whose type error would have been caught if the hook had `&&`.

**Diagnosis:** run the hook script with `bash -x .husky/pre-commit` to see each command's exit code. If commands after a failure still execute, `&&` is missing.

## npm → pnpm migration

To migrate a project from npm to pnpm, see `references/pnpm-migration.md` for the validated step-by-step protocol (backup → import → install → validate → benchmark).

## GitHub Actions CI Workflows

Every repo with code MUST have a `.github/workflows/ci.yml`. Ticket `t_74a9b1a9` (hermes-ops) tracks the rollout — blocked until pre-push hooks (`t_91a0d8bd`) are in place.

### Node/TS Workflow Template

```yaml
name: CI
on:
  push:
    branches: [main]
    paths-ignore: ['**.md', '**.txt']
  pull_request:
    branches: [main]
    paths-ignore: ['**.md', '**.txt']

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22' }  <!-- ⚠️ Must match engines.node in package.json -->
      - run: npm ci  # or pnpm install --frozen-lockfile
      - run: npx playwright install --with-deps
```

**⚠️ `--with-deps` is for ephemeral CI runners only.** GitHub Actions runners
are fresh VMs — system dependencies must be installed every run. On persistent
hosts (VPS, dev machines), the system deps are already installed and persist
across reboots. On those hosts, use plain `npx playwright install chromium`
(~1.5s cache hit) instead of `--with-deps` (~55s of wasted `apt-get update`).
Set `PLAYWRIGHT_BROWSERS_PATH` globally to point all projects at a shared
browser cache and add it to Hermes `terminal.env_passthrough` so subagent
shells inherit it.

- `vitest run` → vitest step
      - run: tsc --noEmit
      - run: npm run lint
      - run: playwright test --workers=1
```

### Python Workflow Template

```yaml
name: CI
on:
  push:
    branches: [main]
    paths-ignore: ['**.md', '**.txt']
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: pytest
```

### Godot Workflow Template

```yaml
name: CI
on:
  push:
    branches: [main]
    paths-ignore: ['**.md', '**.txt']
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: barichello/godot-ci@v4
        with: { godot-version: '4.3' }
      - run: godot --headless --quit --path .
```

### Swift Workflow Template

```yaml
name: CI
on:
  pull_request:
    branches: [main]  # Only on PR — macOS runners are 10× cost

jobs:
  ci:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - run: swift test
```

### HTML/Docs Only

Skip CI. If a workflow file exists at all, use a minimal pass-through:

```yaml
name: CI
on: [push, pull_request]
jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - run: 'echo "No tests — docs only repo"'
```

### CI Checklist (per repo)

- [ ] `.github/workflows/ci.yml` exists and matches the repo's stack
- [ ] `paths-ignore` set for docs-only changes
- [ ] CI badge in README.md
- [ ] Branch protection: require CI green before merge to main
- [ ] No secrets needed (all public repos)
- [ ] Cache `node_modules`/`.pnpm-store` for Node repos (actions/cache@v4)

## GitHub Actions: npm → pnpm workflow

When a project has already been migrated to pnpm but the CI workflow still uses `bahmutov/npm-install@v1` and `npm run`, see `references/github-actions-pnpm-workflow.md` for the complete conversion recipe (action replacement, `--if-present` pitfall, `pnpm-workspace.yaml` trap).

## Long-Running Test Execution

For running full test suites without burning agent iteration budget, use the `background + notify + wait` pattern. See `references/long-running-tests.md` for the complete pattern, examples, and pitfalls.

## Bulk Dependency Updates

For bulk-merging dozens of dependency PRs or running `npm-check-updates` pipelines, see `references/dependency-bulk-updates.md` and `references/breaking-changes-catalog.md` for migration recipes for Express 5, Prisma 7, Stripe 22, React Router 7, and other breaking upgrades.
