# Playwright E2E Test Flake Diagnosis

Patterns for diagnosing why an E2E test fails in CI but passes sometimes locally,
or why it times out on a specific locator.

## Fastest Diagnostic: Read error-context.md

Playwright saves `error-context.md` in the test results directory. It includes a
**page snapshot** (YAML dump of the accessibility tree at failure time). This is
more informative than the stack trace alone — it shows what was actually on screen.

```
test-results/<test-name>-chromium-retry<N>/error-context.md
```

The `# Page snapshot` section shows the actual rendered DOM as Playwright sees it.
Compare what's there vs what the test expects.

## When Page Snapshot Shows "Internal Server Error"

The server crashed during the request. This is NOT a DOM/locator issue.

1. Check the server stderr output — the root cause is logged there.
2. Common cause: missing env vars in `playwright.config.ts` → `webServer.env`.
   The server runs as a subprocess with only the env vars you explicitly pass.
3. Compare env var requirements in the project's schema (e.g., `env.server.ts`
   Zod schema) against what `webServer.env` provides.
4. The `start:mocks` script may hardcode `NODE_ENV=production` which changes
   which env vars are required (e.g., `SESSION_SECRET` optional in test,
   required in production).

## When Page Snapshot Shows Login Page Instead of App Content

The user isn't authenticated. The test's `login()` fixture creates a session
cookie, but the server doesn't accept it.

- **Cause:** `SESSION_SECRET` differs between the test process (which creates
  the cookie) and the webServer subprocess (which validates it).
- **Fix:** Set the same `SESSION_SECRET` in BOTH:
  - `process.env.SESSION_SECRET` (test process, before `dotenv/config`)
  - `webServer.env.SESSION_SECRET` (server subprocess)

## `.count()` Does Not Auto-Wait

```ts
// ❌ Flaky — counts immediately, before results render
const buttons = page.getByRole('button', { name: /import/i })
const count = await buttons.count()
expect(count).toBeGreaterThan(0)

// ✅ Wait for visibility first, then count
const buttons = page.getByRole('button', { name: /import/i })
await expect(buttons.first()).toBeVisible()  // auto-waits
const count = await buttons.count()
expect(count).toBeGreaterThan(0)
```

`expect().toBeVisible()` auto-waits (retries until visible or timeout).
`.count()` queries immediately — no retry, no wait.

## `.first()` May Target the Wrong Button

When a page has multiple buttons with the same accessible name (e.g., a global
header "Search" button AND a form's "Search" submit button), `.first()` returns
the first in DOM order, which may not be the one you want.

```ts
// ❌ Ambiguous — may click the header search instead of the form
await page.getByRole('button', { name: /search/i }).first().click()

// ✅ Scoped to the specific form
await page.locator('form[method="post"]').getByRole('button', { name: /search/i }).click()
```

Scope the locator to the containing element (form, card, section) instead of
grabbing the nth match on the whole page.

## Relationship to e2e-testing skill

For a broader diagnosis flow covering CI setup, `@slow` timeouts, shared DB isolation, and `cross-env` precedence, load the `e2e-testing` skill. This reference is a quick lookup; the skill is the full workflow.

## CI-Specific: Missing `CI=true` in Workflow

Playwright configs commonly branch on `process.env.CI` for webServer command selection.
If the CI workflow doesn't set `CI: true` in the job `env`, the config falls back to
`npm run dev` which uses `tsx watch --inspect` — dev server, debug port, no server reuse.
**Check the workflow YAML first** when a test passes locally but fails on CI.

## `@slow` Tag Does NOT Extend Timeout

The global `timeout` in `playwright.config.ts` applies to all tests regardless of tags.
## Server Env Var Mismatch Checklist

When the E2E server starts but returns errors:

1. Read `webServer.command` and trace what it actually runs (npm script → cross-env → tsx/node).
2. Read the env validation schema (typically `app/utils/env.server.ts`).
3. List every `z.string()` field — those are required.
4. Check which become optional in test/dev vs production.
5. Set ALL required vars in `webServer.env` AND `process.env` (for test fixtures that also need them).
6. `SESSION_SECRET` must be IDENTICAL in both places.
7. **Check `.env` precedence:** `dotenv/config` in the entry point loads `.env` but does NOT override existing vars. Playwright's `webServer.env` values take precedence. However, `cross-env` in npm scripts CAN override both — check the npm script for hardcoded `NODE_ENV=production` or similar overrides.
8. **Check if CI workflow copies `.env.example` → `.env`:** If the workflow does `cp .env.example .env`, verify `.env.example` has all required vars. Missing `SESSION_SECRET` in `.env.example` is a common issue when the CI job doesn't set it in `env:`.
