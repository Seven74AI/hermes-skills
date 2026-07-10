# Running and debugging E2E tests

## Prerequisites

`.env` must include:
```
DATABASE_URL="file:./data/data.db"
CACHE_DATABASE_PATH="./other/cache.db"
LITEFS_DIR=/tmp          # ⚠️ Required — SSR crashes without it
SESSION_SECRET="..."
HONEYPOT_SECRET="..."
MOCKS=true
# ... other mock env vars
```

## Commands

```bash
# Full E2E suite
LITEFS_DIR=/tmp npm run test:e2e:run

# Specific test file
LITEFS_DIR=/tmp npx playwright test tests/e2e/playlists.test.ts --reporter=line

# Specific tests by name pattern
LITEFS_DIR=/tmp npx playwright test tests/e2e/playlists.test.ts --grep "does not show" --reporter=line

# Run locally with CI=true (matches CI behavior — uses start:mocks, reuseExistingServer)
LITEFS_DIR=/tmp CI=true npx playwright test --grep "profile photo"

# With UI (debugging)  
LITEFS_DIR=/tmp npx playwright test --ui
```

## ⛔ webServer.env must include ALL required env vars

`npm run start:mocks` runs with `NODE_ENV=production`, which makes `SESSION_SECRET`, `DATABASE_PATH`, `CACHE_DATABASE_PATH`, `INTERNAL_COMMAND_TOKEN`, and `HONEYPOT_SECRET` required by `env.server.ts` validation. The `webServer.env` config in `playwright.config.ts` must provide ALL of them:

```ts
// playwright.config.ts — webServer.env
env: {
    PORT,
    NODE_ENV: 'test',
    MOCKS: 'true',
    YOUTUBE_MOCKS: 'true',
    DATABASE_URL: `file:${BASE_DATABASE_PATH}`,
    DATABASE_PATH: BASE_DATABASE_PATH,
    CACHE_DATABASE_PATH: path.join(process.cwd(), './tests/prisma/cache.db'),
    INTERNAL_COMMAND_TOKEN: 'test-internal-token',
    HONEYPOT_SECRET: 'test-honeypot-secret',
    SESSION_SECRET: 'test-session-secret',
},
```

**Symptom when missing:** Every request returns 500 with `<body>Internal Server Error</body>`. Server stderr shows `❌ Invalid environment variables: { DATABASE_PATH: ['Required'], ... }`. The page snapshot in `error-context.md` shows `- generic [ref=e2]: Internal Server Error`.

## ⛔ SESSION_SECRET must match between test process and webServer

The test process (Playwright test runner) creates session cookies via the `login()` fixture using `authSessionStorage`, which reads `SESSION_SECRET` from `process.env`. The webServer subprocess validates those cookies using ITS `SESSION_SECRET`. If they differ, the server rejects the cookie and the user is never authenticated.

```ts
// playwright.config.ts — must set BOTH:
// 1. For the test process (before dotenv/config)
process.env.SESSION_SECRET = 'test-session-secret'

// 2. For the webServer subprocess
webServer: {
    env: {
        SESSION_SECRET: 'test-session-secret',  // MUST match #1
    }
}
```

**Symptom when mismatched:** Page snapshot shows login form (`"Welcome back!"`, username/password fields) instead of the target page. The test fails with `locator.getByRole('main').getByRole('img')` timeout because the profile page never rendered.

## Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `LITEFS_DIR is not defined` | Missing env var | Add `LITEFS_DIR=/tmp` to `.env` or export |
| All requests return 500 | Dev server crashes on SSR startup | Usually missing env vars; check `.env` completeness |
| `Invalid environment variables` | Zod validation failure | Ensure all required env vars are set in `.env` AND webServer.env |
| Tests pass but against error pages | `getInstanceInfoSync` crash before app init | Add `LITEFS_DIR` — false negatives |
| `Internal Server Error` in page snapshot | webServer.env missing required vars | Add `DATABASE_PATH`, `SESSION_SECRET`, etc. to webServer.env |
| Login form shown instead of target page | SESSION_SECRET mismatch between test process and webServer | Set identical SESSION_SECRET in both `process.env` and `webServer.env` |

## Playwright anti-patterns

### ⛔ `.count()` doesn't auto-wait

```ts
// WRONG — queries immediately, returns 0 before results render
const buttons = page.getByRole('button', { name: /import/i })
const count = await buttons.count()  // always 0 if results haven't loaded

// RIGHT — wait for visibility first, then count
await expect(buttons.first()).toBeVisible()  // auto-waits up to timeout
const count = await buttons.count()
```

### ⛔ `.first()` on ambiguous locators

When multiple elements match the same role+name, `.first()` picks the first in DOM order, which may not be the intended target:

```ts
// WRONG — matches the global header search button (first in DOM)
await page.getByRole('button', { name: /search/i }).first().click()

// RIGHT — scope to the specific form
await page.locator('form[method="post"]').getByRole('button', { name: /search/i }).click()
```

### ⛔ `waitForTimeout` is a flake magnet

Fixed-time waits (`page.waitForTimeout(500)`, `page.waitForTimeout(1000)`) are unreliable on slow CI. Playwright's `expect(…).toBeVisible()` and other web-first assertions auto-wait up to the test timeout. Every `waitForTimeout(N)` should be replaced with an `expect` that naturally auto-waits.

### ⛔ `@slow` tag doesn't extend test timeout

The `@slow` tag is just a label for test filtering — it does NOT change the test timeout. The global config `timeout: 15000` applies to all tests. Long flows (onboarding, passkey registration) need explicit `test.setTimeout(30000)`.

### ⛔ `waitForURL` pre-creation pattern is fragile

Creating `page.waitForURL()` BEFORE clicking submit, then awaiting in try/catch, silently times out when the form returns `data()` (same-page re-render) instead of `redirect()`. Remix actions that return `data()` trigger no URL change. Instead: click first, then `await page.waitForURL(…)` directly.

## Diagnostic workflow

When an E2E test fails:

1. **Read `error-context.md` first** — it contains the page snapshot at failure time. The snapshot tells you exactly what the page rendered (error page, login form, correct page missing elements).

2. **Check the page snapshot for `Internal Server Error`** — this means the server crashed during SSR. Check server stderr for the actual error.

3. **Check the page snapshot for login form** — if you see `"Welcome back!"` and username/password fields, the user isn't authenticated. SESSION_SECRET mismatch.

4. **Check for wrong page content** — if the page renders but the wrong page (e.g., `/search` instead of YouTube import), a locator is targeting the wrong element.

5. **Run the test locally** before pushing fixes. CI feedback loops are slow; local `CI=true npx playwright test --grep "test name"` gives sub-minute feedback.

## CI Playwright job

The CI workflow's Playwright job must set `CI: true`:

```yaml
- name: 🎭 Playwright tests
  run: npx playwright test --shard=${{ matrix.shard }}/${{ strategy.job-total }}
  env:
    CI: true
    MOCKS: true
```

Without `CI=true`, the playwright config falls back to `npm run dev` (dev server with `tsx watch --inspect`), causing debug port conflicts, slower startup, and `reuseExistingServer: false`.
