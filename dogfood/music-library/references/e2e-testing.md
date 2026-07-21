# Running E2E tests

## Prerequisites

`.env` must include:

```
DATABASE_URL="file:./data.db?connection_limit=1"
DATABASE_PATH="./prisma/data.db"
CACHE_DATABASE_PATH="./other/cache.db"
LITEFS_DIR="/litefs/data"
SESSION_SECRET="***"
HONEYPOT_SECRET="***"
INTERNAL_COMMAND_TOKEN="***"
# Tigris/S3 mock vars...
```

## Commands

```bash
# Full E2E suite
LITEFS_DIR="/litefs/data" npm run test:e2e:run

# Specific test file
LITEFS_DIR="/litefs/data" npx playwright test tests/e2e/playlists.test.ts --reporter=line

# Specific tests by name pattern
LITEFS_DIR="/litefs/data" npx playwright test tests/e2e/playlists.test.ts --grep "does not show" --reporter=line

# Run locally with CI=true (matches CI behavior — uses start:mocks, reuseExistingServer)
LITEFS_DIR="/litefs/data" CI=true npx playwright test --grep "profile photo"

# With UI
LITEFS_DIR="/litefs/data" npx playwright test --ui
```

## webServer.env config

`playwright.config.ts` must provide all required env vars for the server subprocess:

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

`SESSION_SECRET` must be identical in both `process.env` (test process, before `dotenv/config`) and `webServer.env` (server subprocess).

## CI Playwright job

```yaml
- name: 🎭 Playwright tests
  run: npx playwright test --shard=${{ matrix.shard }}/${{ strategy.job-total }}
  env:
    CI: true
    MOCKS: true
```

## Common test utilities

### Dismiss install banner

The PWA install banner renders at `z-30` and can intercept clicks on the bottom nav (z-40) or be covered by the audio player (z-50). Use `{ force: true }` to click through overlays:

```ts
async function dismissInstallBanner(page: import("@playwright/test").Page) {
  const installBanner = page.getByRole("region", { name: "Install app" });
  if (await installBanner.isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "Not now" }).click({ force: true });
  }
  // Remove Radix toast notifications that intercept pointer events
  await page.evaluate(() => {
    const region = document.querySelector('[aria-label="Notifications (F8)"]');
    if (region) region.remove();
  });
}
```

Call this before interacting with bottom-positioned elements (nav, player mini bar) on mobile viewports.

### Close lingering dialogs between tests

Previous tests can leave Radix dialogs/sheets open, causing their overlay (fixed inset-0 z-50) to intercept clicks in subsequent tests. Press Escape before any test that interacts with a dialog:

```ts
await page.keyboard.press("Escape");
await page.waitForTimeout(300);  // let animation complete
```
