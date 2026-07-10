---
name: e2e-testing
description: Diagnose and fix flaky Playwright/Cypress E2E tests. Use when user says "flaky test", "E2E failure", "Internal Server Error in test", or a Playwright/Cypress test is failing intermittently.
version: 1.0.0
---

# E2E Testing

Diagnose and fix flaky end-to-end tests. Covers Playwright config issues, env var mismatches, auth fixture failures, and CI-vs-local discrepancies.

## Phase 0 — Run locally before pushing. Do not assume.

**Never push a fix to CI without running the test locally first.** CI is for verification, not primary testing. Pushing guessed fixes and waiting for GitHub runners is slow and wastes time. If you can't run the test locally, figure out why — missing env vars, build step, wrong command — and fix that first. A local feedback loop is seconds; a CI loop is minutes (or longer with queue delays).

**Do not assume what the bug is.** Read the actual error output — check `error-context.md` for the page snapshot, check CI logs (not just the summary), run the test yourself. Guessing `waitForTimeout` or `waitForURL` when you haven't seen the page screenshot is worse than doing nothing — it introduces anti-patterns that hide the real cause.

**Check CI logs when told still failing.** When the user says "still failing," pull the actual CI run logs — don't assume the failure is from your branch. The CI may be running old code on `main`, or your branch may not have triggered CI at all (workflow only fires on `push` to main/dev or `pull_request`). If there are no runs for your branch, tell the user and open a PR.

## Common Pitfalls

### 1. "Internal Server Error" on every page

**Check the error context file** first (`test-results/<test-name>-retryN/error-context.md`). The `# Page snapshot` section tells you exactly what rendered:

- `Internal Server Error` → server crashed on startup. Check env vars.
- Login screen ("Welcome back!") → `login()` fixture failed. Check `SESSION_SECRET` match.
- Vite `virtual:react-router/server-build` error → `NODE_ENV` mismatch. Server tried to use Vite dev mode instead of production build.

To debug the server: run `npm run start:mocks` manually, capture stderr, and curl a page:
```bash
npm run start:mocks > /tmp/stdout.log 2> /tmp/stderr.log &
sleep 10
curl -s http://localhost:3000/settings/profile
cat /tmp/stderr.log | grep "Invalid environment variables" -A 10
```

### 2. SESSION_SECRET mismatch between test process and webServer

The Playwright config has **two separate environments** that must share the same `SESSION_SECRET`:

- **Test process** (`process.env` at the top of `playwright.config.ts`) — runs fixtures like `login()` that create session cookies
- **webServer subprocess** (`webServer.env` in `defineConfig()`) — runs the app server that validates those cookies

If `SESSION_SECRET` differs, the cookie is invalid and the user is never logged in. The page silently redirects to `/login`.

**Fix:** Set `SESSION_SECRET` (and all required env vars from `env.server.ts`) in **both** locations with the **same value**.

### 3. Missing required env vars when NODE_ENV=production

When the `start:mocks` script uses `NODE_ENV=production`, env validation (e.g. `env.server.ts` → `init()`) may require vars that are optional in dev/test. Common required vars:
- `DATABASE_PATH`
- `DATABASE_URL`
- `CACHE_DATABASE_PATH`
- `INTERNAL_COMMAND_TOKEN`
- `HONEYPOT_SECRET`
- `SESSION_SECRET` (required in production, optional in test/dev)
The server crashes silently with "Internal Server Error" if any are missing.

### 4. CI missing `CI=true` → dev server instead of production

Playwright configs commonly branch on `process.env.CI`:
```ts
webServer: {
    command: process.env.CI ? 'npm run start:mocks' : 'npm run dev',
}
```
Without `CI: true` in the workflow's `env`, the webServer runs `npm run dev` which:
- Uses `tsx watch --inspect` (debug port 9229)
- Loads Vite middleware instead of pre-built assets
- Doesn't reuse the server across workers (`reuseExistingServer: !!process.env.CI`)
- Fails silently or produces different behavior than production

**Fix:** Add `CI: true` to the Playwright job's `env` in the workflow YAML.

### 4. `@slow` tag does NOT extend timeout

Playwright `@slow` / `@smoke` tags are just labels — they don't affect timeouts. The global `timeout` in `playwright.config.ts` applies to ALL tests. Long flows (onboarding → email verify → fill form → submit → redirect, or passkey register → logout → login → delete → retry) easily exceed 15s.

**Fix:** Add `test.setTimeout(30000)` at the top of tests that need more time:
```ts
test('long flow', { tag: '@slow' }, async ({ page }) => {
    test.setTimeout(30000)  // override global 15s
    // ...
})
```

### 5. Shared DB state between parallel tests

E2E tests sharing a SQLite database can't assume clean state. A test that checks "no cookies uploaded yet" will flake if another test in the same shard already imported cookies. The page snapshot in `error-context.md` shows the actual rendered text — use it as the source of truth.

**Fix:** Don't assert count=0 or absence of data. Assert that the section renders (e.g., "Current State" heading + "Cookies on disk" text), not specific numeric values.

### 6. `cross-env` in npm scripts overrides webServer.env

When `webServer.command` is `npm run start:mocks`, and that script uses `cross-env NODE_ENV=production`, the `cross-env` value **overrides** whatever `NODE_ENV` you set in `webServer.env`. This can change which env vars are required (e.g., `SESSION_SECRET` optional in test, required in production).

**Fix:** Either don't use `cross-env` for values that matter, or accept the override and provide the required vars.

When the `start:mocks` script uses `NODE_ENV=production`, env validation (e.g. `env.server.ts` → `init()`) may require vars that are optional in dev/test. Common required vars:
- `DATABASE_PATH`
- `DATABASE_URL`
- `CACHE_DATABASE_PATH`
- `INTERNAL_COMMAND_TOKEN`
- `HONEYPOT_SECRET`
- `SESSION_SECRET` (required in production, optional in test/dev)

The server crashes silently with "Internal Server Error" if any are missing.

### 8. waitForTimeout / waitForURL are anti-patterns

`waitForTimeout(500)` and pre-created `waitForURL` with generous timeouts are NOT fixes for flaky tests — they mask timing issues. If removing a `waitForTimeout` breaks the test, find the real synchronization gap (missing `expect` auto-wait, missing MSW handler, stale state).

## Diagnosis Flow

1. Read `error-context.md` → check `# Page snapshot`
2. If server error → check stderr for env validation failures
3. If login page → verify `SESSION_SECRET` matches between test process and webServer
4. If page renders but element not found → check the actual page snapshot for what IS rendering
5. Run the test locally with `--grep "test name"` to iterate fast
6. Only push to CI after local confirmation

See `references/playwright-env-vars.md` for the full Playwright env var debugging reference.
