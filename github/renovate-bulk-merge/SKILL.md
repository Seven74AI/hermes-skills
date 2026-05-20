---
name: renovate-bulk-merge
description: "Bulk-merge renovate dependency PRs: batch minors, individual majors. Also covers npm-check-updates pipeline for stale branches."
version: 1.2.0
author: Hermes Agent
platforms: [linux]
tags: [renovate, npm, dependencies, bulk-merge, github]
related_skills: [github-auth, github-pr-workflow]
---

# Renovate Bulk Merge

Safely merge dozens of renovate dependency PRs into a fork or upstream repo.

## Prerequisites

- Fork/clone of target repo with upstream remote configured
- Node.js + npm available
- GitHub auth: use git credential helper (`~/.git-credentials`) or `GITHUB_TOKEN` env var
- Tests must be runnable (`.env` configured, DB migrated)
- `npx npm-check-updates` installed (`npm install -g npm-check-updates`)

## Decision: renovate branches vs npm-check-updates

**Use `npm-check-updates`** when renovate PRs are stale (> 1 month) — merging 70+ branches individually is far slower and the end result is identical. Apply in 3 phases, testing after each.

### npm-check-updates pipeline (preferred for stale branches)

```bash
# Phase 1: batch all minors/patches (safe — backwards-compatible)
npx npm-check-updates -t minor -u
npm install && npx prisma generate --sql && npx vitest run
# If passes → git commit -m "chore: batch minor/patch npm updates"

# Phase 2: batch "likely safe" majors
# These almost never break anything:
npx npm-check-updates -f "dotenv,glob,remix-utils,@paralleldrive/cuid2,set-cookie-parser,cross-env,@types/node,@types/glob,@types/mime-types,@vitejs/plugin-react,@tusbar/cache-control,express-rate-limit,jsdom" -u
npm install && npx prisma generate --sql && npx vitest run
# If passes → commit

# Phase 3: risky majors — one batch, bisect if needed
npx npm-check-updates -f "stripe,typescript,lucide-react,vite,@epic-web/config,@faker-js/faker,@mjackson/*,esbuild,prettier-plugin-*" -u
npm install && npx prisma generate --sql && npx vitest run
# If fails → bisect: revert half the packages, retest, find culprit, handle separately

# Phase 4: known-breaking upgrades (handle individually with code fixes)
# Express 5, Prisma 7 — see Common pitfalls for fix recipes
```

**Use renovate branches** only when PRs are recent (< 2 weeks) and you need individual review/attribution.

## Step 1: Fetch & categorize (renovate branches approach)

```bash
cd /path/to/repo
git checkout main && git pull origin main
git fetch upstream
```

List all renovate branches and categorize by impact:

```bash
for branch in $(git branch -r | grep 'upstream/renovate' | sed 's|upstream/||'); do
  echo "=== $branch ==="
  # Check if it touches package.json (not just lockfile)
  has_pkg=$(git diff main...upstream/$branch --name-only | grep -c 'package.json$')
  stat=$(git diff main...upstream/$branch --stat | tail -1)
  echo "  package.json: $has_pkg | $stat"
done
```

### Categorization rules:
- **Lockfile-only** (no package.json change, < 10 lines): SAFE — batch merge
- **Patch bumps** (package.json touched, < 20 lines diff): SAFE — batch merge  
- **Standard bumps** (package.json touched, 20-200 lines): Review individually
- **Major bumps** (package.json touched, > 200 lines AND/OR branch name contains `major-`): HANDLE ONE-BY-ONE

## Step 2: Batch minor bumps

For lockfile-only and small patch bumps, merge all at once:

```bash
git checkout -b batch/renovate-minors

for branch in $SAFE_BRANCHES; do
  git merge "upstream/$branch" --no-edit || {
    # Resolve lockfile conflicts by accepting incoming
    git checkout --theirs package-lock.json 2>/dev/null
    git add package-lock.json
    git commit --no-edit
  }
done

npm install
npx prisma generate --sql  # if using Prisma
npx vitest run             # or npm test

# If all tests pass:
git checkout main && git merge batch/renovate-minors --no-edit
git push origin main
```

## Step 3: Major bumps — one at a time

For each major bump, create a dedicated branch, merge, fix, test:

```bash
git checkout main
git checkout -b fix/SOMETHING-vX
git merge upstream/renovate/major-SOMETHING-monorepo --no-edit
# Resolve lockfile if needed:
git checkout --theirs package-lock.json && git add package-lock.json && git commit --no-edit

npm install
npx prisma generate --sql

# TEST BEFORE PROCEEDING
npx vitest run
# If ANY test fails, investigate before continuing

# If OK, merge to main:
git checkout main && git merge fix/SOMETHING-vX --no-edit
```

## E2E tests (optional but recommended)

After all merges, rebuild and run e2e:

```bash
npm run build
# Start server in background with MOCKS + env vars:
set -a && source .env && set +a
NODE_ENV=production MOCKS=true PLAYWRIGHT_TEST_BASE_URL=http://localhost:3000 \
  node ./server-build/index.js &
sleep 3
npx playwright test --workers=1
```

## CI validation strategy

**Run CI on your fork FIRST, then update the upstream PR.** This catches issues before the upstream CI even sees them.

### Enable CI on your fork

If the fork doesn't run CI automatically on push (common for newly forked repos), add `workflow_dispatch: {}` to the workflow triggers:

```yaml
on:
  push:
    branches: [main]
  pull_request: {}
  workflow_dispatch: {}  # <-- add this
```

Then push and trigger manually:

```bash
gh workflow run deploy.yml --repo Seven74AI/shop --ref main
# or via API:
curl -X POST -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/repos/OWNER/REPO/actions/workflows/deploy.yml/dispatches" \
  -d '{"ref":"main"}'
```

### Fork PR workflow approval

When opening a PR from a fork to upstream, GitHub may require the upstream maintainer to manually approve the workflow run. The CI will show "Waiting for approval" until they click "Approve and run". This is a GitHub security feature for first-time contributors.

### Cron watchdog for upstream PR CI

To auto-monitor and fix CI failures on an upstream PR while waiting:

```bash
hermes cron create --name "CI watchdog — upstream PR" --schedule "every 10m" --repeat 10 \
  --prompt "Check CI on PR #N of upstream/repo. If any check fails, pull logs, fix the code in /path/to/local/clone, test locally, commit, push."
```

This works best with git credential helper so the cron agent can push fixes autonomously.

## Common pitfalls

- **Parallel agents on same repo** → chaos. If using delegate_task for parallel work, each agent MUST have its own `git clone` of the repo (e.g. `/tmp/shop-agent-1`, `/tmp/shop-agent-2`). Same repo + different branches = lockfile wars. Clone like: `git clone /tmp/main-repo /tmp/agent-N`.
- **Express 5** breaks bare `*` wildcard routes. Fix: change `'*'` to `'{*path}'` everywhere in route definitions (`server/index.ts`). Check for `app.get('*')`, `app.all('*')`, `app.get(['/img/*'])` — all need named wildcards.
- **Prisma v7** requires:
  1. Create `prisma.config.ts` with `datasource: { url: process.env.DATABASE_URL ?? 'file:./prisma/data.db' }`
  2. Remove `url` from `prisma/schema.prisma` datasource block
  3. Install adapter: `npm install @prisma/adapter-libsql`
  4. Update `db.server.ts`: `import { PrismaLibSql } from '@prisma/adapter-libsql'` then `new PrismaClient({ adapter: new PrismaLibSql({ url: ... }) })`
  5. Remove `?connection_limit=1` from DATABASE_URL — libsql adapter doesn't support it
  6. `prisma migrate reset --force` no longer supports `--skip-seed` flag
- **Vitest 4** can't bundle `node:*` builtins. `test.server.deps.external`, `test.ssr.external`, and `resolve.external` do NOT work for this in Vitest 4. The ONLY reliable fix is this Vite plugin in `vite.config.ts`:
  ```ts
  function externalizeNodeBuiltins() {
    return {
      name: 'externalize-node-builtins',
      enforce: 'pre' as const,
      resolveId(id: string) {
        if (id.startsWith('node:')) return { id, external: true }
        return null
      },
    }
  }
  // Add to plugins array as first plugin
  ```
- **Sentry v10** requires `@opentelemetry/instrumentation` peer dep: `npm install @opentelemetry/instrumentation`
- **Email mock for e2e**: `app/utils/email.server.ts` must skip API calls when `MOCKS=true`. Fix the condition from `!RESEND_API_KEY && !MOCKS` to `!RESEND_API_KEY || MOCKS === 'true'`. Also write email fixtures to disk so e2e tests can read them.
- **Storage/S3 mock for e2e**: `app/utils/storage.server.ts` — add `if (process.env.MOCKS === 'true') return key` at the top of `uploadToStorage()`.
- **MSW mocks** only intercept browser-side requests. Server-side calls (OAuth token exchange, S3 uploads) need their own mock logic in production code. Never rely on MSW for e2e server-side operations.
- **GitHub OAuth e2e tests**: cannot work in e2e because `remix-auth-github` does server-side token exchange that MSW can't intercept. These tests exist in unit tests (MSW runs server-side via `setupServer`). Skip them in e2e with `test.skip()`.
- **Rate limiting** in e2e: pass `PLAYWRIGHT_TEST_BASE_URL=http://localhost:3000` to the server process.
- **Lockfile conflicts**: always accept `--theirs` for package-lock.json, then `npm install` to regenerate.
- Always run `npx prisma generate --sql` after npm install (if using Prisma typed SQL).
- **MOCKS mode server startup:**
  ```bash
  set -a && source .env && set +a
  PLAYWRIGHT_TEST_BASE_URL=http://localhost:3000 NODE_ENV=production MOCKS=true \
    node ./server-build/index.js
  ```
  Critical env vars: `RESEND_API_KEY=""`, `GITHUB_CLIENT_ID=MOCK_GITHUB_CLIENT_ID`, `PLAYWRIGHT_TEST_BASE_URL`, `MOCKS=true`
  Note: `process.env.MOCKS` is a string `"true"`, not a boolean. Always compare with `=== 'true'` in server code.
- **GitHub token scope `workflow`** is needed to push changes to `.github/workflows/` files. Without it, `git push` is rejected by GitHub.
- **Playwright parallel workers cause data collisions** — tests that generate unique data (order numbers, categories, usernames) collide with `Unique constraint failed` when `workers > 1`. Always use `npx playwright test --workers=1` in CI for this codebase. The shared SQLite DB and test isolation issues make parallel e2e unreliable.
- **Don't modify `playwright-global-setup.ts` to create a separate test DB** — the CI workflow already has a `migrate` step that prepares the database. Creating a `tests/prisma/play.db` in global setup breaks the assumption that the DB is ready and causes migration/timing issues. Revert to the original global setup (currency/settings upsert only).
- **Breaking changes affect test mocks too**, not just production code. When Stripe v22 changes `apiVersion` or `PaymentStatus` type, update BOTH `app/utils/stripe.server.ts` AND `tests/mocks/stripe.ts`. Same for any library that has mock/stub files in `tests/`.
- **E2E image upload tests need generous timeouts** — `note-images.test.ts` processes image uploads through sharp/streaming, which is slow. Increase `test.setTimeout()` and individual `waitFor`/`expect` timeouts for these tests.
- **Null-safe cookie access in `playwright-utils.ts`** — newer `set-cookie-parser` types may make `cookieConfig` optional. Add `!` assertions or explicit null checks on cookie access patterns.
- **CI DB cache: bust the key** whenever Prisma schema, migration files, or seed data changes. Use a suffix like `-prisma7-v2` to force fresh DB after breaking upgrades.

## Verification checklist

**⚠️ MANDATORY: always reproduce CI failures locally before pushing fixes.** Fixing TypeScript errors by pushing and waiting for CI is slow and error-prone. Run `npx tsc --noEmit`, `npm run lint`, and `npx playwright test --workers=1` locally before each push.

- [ ] `npx vitest run` — all tests pass
- [ ] `npx tsc --noEmit` — no NEW type errors (pre-existing `+types/*` module errors are normal)
- [ ] `npm run lint` — 0 errors (warnings OK)
- [ ] `npm install` succeeds without errors
- [ ] `npx prisma generate --sql` succeeds
- [ ] `npm run build` succeeds
- [ ] Server starts with `NODE_ENV=production MOCKS=true`
- [ ] `curl http://localhost:3000` returns HTTP response (200 or 500 — 500 means server alive, DB not seeded)
- [ ] E2E tests pass locally with `npx playwright test --workers=1` before pushing
- [ ] `.env.example` matches `.env` structure (CI copies `.env.example`)

**Breaking changes quick reference:** see `references/breaking-changes-catalog.md` for fix recipes for Express 5, Prisma 7, Vitest 4, Stripe 22, React Router 7, express-rate-limit 8, set-cookie-parser 3, @epic-web/config 3, Sentry 10.

## Reference files
- `references/breaking-changes-catalog.md` — fix recipes for Express 5, Prisma 7, Stripe 22, React Router 7, etc.
- `references/pr-cleanup-after-consolidation.md` — cleaning up stale PRs after a consolidated merge
- `references/ci-debugging.md` — common CI failure patterns and fixes
- `references/mocks-mode-setup.md` — MOCKS env setup for e2e testing
