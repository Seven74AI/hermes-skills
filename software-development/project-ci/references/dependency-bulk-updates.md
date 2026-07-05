# Bulk Dependency Updates

**This reference was absorbed from the standalone `renovate-bulk-merge` skill (2026-07-05).** Covers safely merging dozens of dependency PRs, npm-check-updates pipeline, and breaking-change migration recipes.

## Decision: renovate branches vs npm-check-updates

**Use `npm-check-updates`** when renovate PRs are stale (> 1 month) — merging 70+ branches individually is far slower and the end result is identical. Apply in 3 phases, testing after each.

### npm-check-updates pipeline (preferred for stale branches)

```bash
# Phase 1: batch all minors/patches (safe — backwards-compatible)
npx npm-check-updates -t minor -u
npm install && npx prisma generate --sql && npx vitest run

# Phase 2: batch "likely safe" majors
npx npm-check-updates -f "dotenv,glob,remix-utils,..." -u
npm install && npx prisma generate --sql && npx vitest run

# Phase 3: risky majors — one batch, bisect if needed
npx npm-check-updates -f "stripe,typescript,lucide-react,vite,..." -u
npm install && npx prisma generate --sql && npx vitest run
# If fails → bisect: revert half, retest, find culprit

# Phase 4: known-breaking upgrades (handle individually with code fixes)
```

**Use renovate branches** only when PRs are recent (< 2 weeks) and you need individual review/attribution.

## Categorization Rules

- **Lockfile-only** (no package.json change, < 10 lines): SAFE — batch merge
- **Patch bumps** (package.json touched, < 20 lines diff): SAFE — batch merge  
- **Standard bumps** (package.json touched, 20-200 lines): Review individually
- **Major bumps** (package.json touched, > 200 lines AND/OR branch name contains `major-`): HANDLE ONE-BY-ONE

## CI Validation Strategy

**Run CI on your fork FIRST, then update the upstream PR.**

If the fork doesn't run CI automatically, add `workflow_dispatch: {}` to the workflow triggers.

## Breaking Changes Quick Reference

See `references/breaking-changes-catalog.md` for fix recipes:
- **Express 5**: bare `*` wildcard routes → `'{*path}'`
- **Prisma v7**: `prisma.config.ts` + adapter (`PrismaBetterSqlite3`, NOT `PrismaLibSql`)
- **Vitest 4**: can't bundle `node:*` builtins → `externalizeNodeBuiltins()` Vite plugin
- **Sentry v10**: requires `@opentelemetry/instrumentation` peer dep
- **Stripe 22**: update both production code AND test mocks

## CI DB Cache

Bust the key whenever Prisma schema, migration files, or seed data changes. Use a suffix like `-prisma7-v2`.

## E2E Tests

After all merges, rebuild and run e2e:
```bash
npm run build
set -a && source .env && set +a
NODE_ENV=production MOCKS=true PLAYWRIGHT_TEST_BASE_URL=http://localhost:3000 \
  node ./server-build/index.js &
sleep 3
npx playwright test --workers=1
```

## Verification Checklist

- [ ] `npx vitest run` — all tests pass
- [ ] `npx tsc --noEmit` — no NEW type errors
- [ ] `npm run lint` — 0 errors (warnings OK)
- [ ] `npm install` succeeds without errors
- [ ] `npx prisma generate --sql` succeeds
- [ ] `npm run build` succeeds
- [ ] Server starts with `NODE_ENV=production MOCKS=true`
- [ ] E2E tests pass locally with `npx playwright test --workers=1` before pushing

## Other references

- `references/mocks-mode-setup.md` — MOCKS env setup for e2e testing
- `references/ci-debugging.md` — common CI failure patterns and fixes  
- `references/pr-cleanup-after-consolidation.md` — cleaning up stale PRs after a consolidated merge
- `references/breaking-changes-catalog.md` — fix recipes for Express 5, Prisma 7, Stripe 22, React Router 7, etc.
