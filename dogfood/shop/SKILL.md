---
name: shop
description: "Shop project configuration — tech stack, repo, PR, testing."
version: 1.0.0
metadata:
  hermes:
    tags: [shop, project, ecommerce, reference]
---

# Shop — Project Configuration

E-commerce project. Load this skill when working on the Shop codebase.

## GitHub

- Repo: `Seven74AI/shop`
- Working copy: `/tmp/shop-original`
- Git remote: `https://oauth2:TOKEN@github.com/Seven74AI/shop.git` (token from main Hermes env)
- Last merged PR: `mnlamart/shop#99` (consolidated — Node 24, pnpm fix, a11y, e2e, seed config) — merged 2026-05-19, all CI green
- Open PR: `mnlamart/shop#100` (Chore/cleanup sweep by mnlamart, 2026-05-19)

## Environment

- `MOCKS=true` — all external services mocked
- `GITHUB_TOKEN` in `.env` = **application OAuth** (GitHub login feature, `api.github.com`), NOT a git push token. Git push uses the remote URL token.

## Tech Stack

- **Runtime:** Node.js, Express 5
- **ORM:** Prisma 7
- **Testing:** Vitest 4, Playwright
- **Payments:** Stripe 22
- **Mocks:** `MOCKS=true` (enabled in dev)

## Test Suite

- 283 unit tests + 117 e2e tests

## CI

Full CI after dependency changes: `vitest run + tsc --noEmit + lint + playwright test --workers=1`

## Prisma — Adapter & Config Pitfalls

### Prisma v7 — Use `PrismaBetterSqlite3`, NOT `PrismaLibSql`

Shop uses `@prisma/adapter-better-sqlite3` with `PrismaBetterSqlite3` (same as music-library). The chain is:

```
PrismaClient → PrismaBetterSqlite3 adapter → better-sqlite3
```

**Why NOT `@prisma/adapter-libsql`:** The libsql adapter (`PrismaLibSql`) causes `Operation has timed out` on ALL Prisma queries in GitHub Actions CI (Ubuntu 24.04, Node 24). The `@libsql/client` native stack fails to connect to local SQLite files in CI, even though it works locally. Music-library's CI passes with `PrismaBetterSqlite3` — mirror that pattern.

```ts
// app/utils/db.server.ts
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3'

const adapter = new PrismaBetterSqlite3({
  url: process.env.DATABASE_URL ?? 'file:./prisma/data.db',
})
```

### `better-sqlite3` MUST be in `onlyBuiltDependencies` (pnpm v10+)

pnpm v10+ uses `pnpm.onlyBuiltDependencies` from `package.json` — this takes precedence over `allowBuilds` in `pnpm-workspace.yaml`. If `better-sqlite3` isn't in `onlyBuiltDependencies`, its native module never compiles, causing `Could not locate the bindings file` at runtime.

```json
// package.json
"pnpm": {
  "onlyBuiltDependencies": [
    "@prisma/engines",
    "better-sqlite3",   // ← REQUIRED
    "esbuild",
    "prisma",
    "sharp"
  ]
}
```

**Symptom without it:** `Error: Could not locate the bindings file. Tried: .../better-sqlite3/.../better_sqlite3.node` (12+ paths, all missing).

### Prisma v7 — `prisma.config.ts` overrides `package.json`

When `prisma.config.ts` exists, Prisma CLI **ignores** `prisma.seed` in `package.json`. The seed must be configured in the config file:

```ts
// prisma.config.ts
export default defineConfig({
  datasource: { url: '...' },
  migrations: {
    seed: 'tsx prisma/seed.ts',  // ← REQUIRED here, NOT in package.json
  },
})
```

**Symptom:** `prisma db seed` says "No seed command configured" even though `package.json` has `"prisma": { "seed": "..." }`.

### `packageManager` must be exact version

```json
// ❌ Wrong — causes "Cannot switch to pnpm@10: 10 is not a valid version"
"packageManager": "pnpm@10"

// ✅ Correct
"packageManager": "pnpm@10.9.0"
```

CI workflows using `pnpm/action-setup@v6` with `version: 10` install pnpm 10.x fine, but the invalid `packageManager` field causes warnings on every pnpm command.

## Pitfall: Manual GitHub merge ≠ Kanban completion

The kanban block watchdog has **no bridge to GitHub**. If you manually merge a PR that a kanban task was blocked on, the kanban task stays `blocked` and the watchdog keeps escalating (every 5 min). **ALWAYS complete the kanban task after a manual merge**:

```bash
hermes kanban --board shop unblock <task_id>
hermes kanban --board shop complete <task_id>
```

Also check child tasks — they may be `ready` and waiting on the completed parent.

## Active Tasks

- **Board: 72 tickets (66 issues + 6 recette branches)** across 6 phases for production-readiness roadmap
- INDEX issue: `mnlamart/shop#167` — master tracking issue, defines phase ordering, dependencies, conventions
- Recette branch workflow: each phase has a `recette/phase-N` merge target. Feature branches merge into recette; one PR per phase to upstream
- **Phase 0 (P0):** #101-105 — typecheck fixes, CI gate, search fix, crash handlers (5 issues, all parallel except #103 blocked by #101+#102)
- **Phase 1 (P1):** #106-133 — VAT, invoices, GDPR, returns, i18n, legal pages (28 issues with dependency chains)
- **Phase 2 (P2):** #134-141 — reliability: idempotency, logging, pagination, backups, staging, metrics, email
- **Phase 3 (P3):** #142-150 — security hardening: CSP, headers, upload verification, audit log, 2FA
- **Phase 4 (P4):** #151-161 — competitive features: FTS5 search, reviews, promotions, SEO
- **Phase 5 (P5):** #162-166 — operational excellence: ADRs, scaling, feature flags, circuit breakers, DR
- **Dependencies:** 75 intra-board links created from each issue's `Blocks:` / `Blocked by:` fields
- **Dispatch rule:** lowest-numbered phase first, priority:critical within phase, only advance when phase has zero critical open
- See `references/issue-to-kanban-workflow.md` for the batch creation + dependency parsing pattern

## PR Consolidation

When multiple open PRs on `mnlamart/shop` overlap (e.g., dep bumps + pnpm migration + CI workflow fixes), consolidate into one PR:

1. Check which PRs are already merged on main (via `gh pr view` + `git log`)
2. Apply remaining changes onto a single branch off `mnlamart/main`
3. Run full local CI: `CI=true pnpm lint && CI=true pnpm typecheck && CI=true pnpm test -- --run`
4. Push to `Seven74AI/shop` fork, create PR to `mnlamart/shop` with `gh pr create --repo mnlamart/shop --head Seven74AI:<branch> --base main`
5. Close superseded PRs with comment, or mark as superseded if no close permission

**Pitfall:** `prisma generate` must run before vitest/playwright (build scripts skipped during initial `pnpm install`). Run `CI=true pnpm approve-builds @prisma/engines prisma esbuild sharp @sentry/cli` then `pnpm install` again, then `pnpm exec prisma generate` and `pnpm exec prisma generate --sql`.

**Pitfall:** TypeScript errors may shift after `prisma generate --sql` — typed SQL exports depend on generated client. Always run both generate commands before typecheck.

## Flaky Playwright Test Fixes

Two recurring flaky test patterns in the shop e2e suite. Full session log: `references/flaky-test-patterns.md`.

### Pattern 1: WCAG color-contrast (a11y tests)
Axe-core `color-contrast` violations are inherently flaky in CI — rendering differences between OS/font stacks cause intermittent contrast ratio failures.

**Fix:** Add `{ disableRules: ['color-contrast'] }` to specific `expectPageToBeAccessible()` calls that flake. Follows existing pattern for `button-name` exclusions.

```ts
await expectPageToBeAccessible(page, { disableRules: ['color-contrast'] })
```

### Pattern 2: Prisma transaction race (admin-users)
`prisma.role.upsert()` in a `test.beforeEach()` of a `serial` describe block fails with:
```
Transaction API error: Transaction already closed: A rollback cannot be executed on a committed transaction.
```

**Fix:** Wrap the upsert in try/catch. The role already exists in most runs; the upsert is an idempotent safety net.

```ts
test.beforeEach(async () => {
  try {
    await prisma.role.upsert({ where: { name: 'admin' }, update: {}, create: { name: 'admin', description: 'Administrator' } })
  } catch {
    // Role already exists or transaction conflict — safe to ignore
  }
})
```
