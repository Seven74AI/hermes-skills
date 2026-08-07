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

The PWA install banner renders at z-30 and can intercept clicks on the bottom nav (z-51) or be covered by the audio player (z-50).

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

Previous tests can leave Radix dialogs/sheets open, causing their overlay (fixed inset-0 z-53) to intercept clicks in subsequent tests. Press Escape before any test that interacts with a dialog:

```ts
await page.keyboard.press("Escape");
await page.waitForTimeout(300);  // let animation complete
```

### Pitfall: nested Radix Sheets need multiple Escape presses

Radix primitives open in a stack. Pressing Escape dismisses only the topmost primitive — a Sheet nested inside another Sheet needs two Escapes (one for the inner, one for the outer). This matters because:

1. **`aria-hidden` removes elements from the accessibility tree, not just hides them.** When a Radix Sheet is open, everything outside it gets `aria-hidden="true"`. Playwright's `getByRole` queries the accessibility tree, so those elements resolve to **0 matches** — `toBeVisible()` fails with `Error: element(s) not found`, NOT "element is hidden."

2. **`toBeHidden()` passes for `aria-hidden` elements** (and also for elements not in the DOM), so the pattern `expect(el).toBeHidden()` → Escape → `expect(el).toBeVisible()` looks correct but breaks when there's a nested sheet.

**Example — Overflow sheet inside NowPlaying sheet:**

```ts
// Open the now-playing sheet
await miniBar.getByLabel("Open now playing").click();
const sheet = page.getByTestId("player-now-playing-sheet");
await expect(sheet).toBeVisible();

// Open overflow sheet inside the now-playing sheet
await sheet.getByLabel("More actions").click();

// ❌ WRONG — one Escape only closes overflow, main sheet stays open
//    bottom nav is aria-hidden → getByRole returns 0 elements
await page.keyboard.press("Escape");
await expect(homeLink).toBeVisible(); // "element(s) not found"

// ✓ RIGHT — dismiss both sheets before asserting elements outside them
await page.keyboard.press("Escape"); // Close overflow sheet
await page.keyboard.press("Escape"); // Close now-playing sheet
await expect(homeLink).toBeVisible(); // Back in accessibility tree
```

**Rule of thumb:** count how many Radix overlays the test opened, and press Escape that many times before asserting elements *outside* all of them.

### Pitfall: CSS z-index overlays blocking clicks (not Radix)

When a CSS layer (e.g. a `fixed inset-0 z-52` search overlay) sits above the target element at a lower z-index, Playwright's `click({ force: true })` dispatches the event but the DOM click can still be intercepted by the overlay's pointer-events. The button fires the click handler, but the overlay consumes the event.

**Fix:** Use `page.evaluate` to call `.click()` directly in JavaScript, bypassing all CSS layering:

```ts
// ❌ force:true doesn't help — overlay at z-52 intercepts the click on element at z-50
await page.getByLabel("Open queue").click({ force: true });

// ✓ JavaScript click bypasses CSS pointer-events entirely
await page.evaluate(() => {
  const btn = document.querySelector('[aria-label="Open queue"]') as HTMLButtonElement;
  btn?.click();
});
```

Real case: the search overlay (z-52, fixed inset-0) covered the player bar's "Open queue" button (z-50). `force: true` didn't help — the overlay consumed the click event. `page.evaluate` solved it.
