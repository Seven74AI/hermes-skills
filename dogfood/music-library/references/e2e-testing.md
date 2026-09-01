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

### Dismissing toasts + install banner (shared helpers)

Use the shared helpers in `tests/playwright-utils.ts` — don't re-implement per-test:

```ts
await dismissOverlays(page);        // install banner + any visible toast
await dismissVisibleToasts(page);   // visible toast only
```

`dismissVisibleToasts` clicks the toast body to trigger the click-to-dismiss handler
in `app/components/ui/toaster.tsx`.

**Pitfall — the Radix toast `<li>` has NO `role="status"`.** Radix renders the
screen-reader announcement as a separate `<span role="status" aria-live>`, so
`page.getByRole("status")` does NOT match the toast card. It matches `@dnd-kit`'s
`DndContext` live region (`<div role="status" id="DndLiveRegion-0">`) instead. Target
toasts via `data-testid="toast"` (set on the `<Toast>` root in `toaster.tsx`), never
by role. The toast viewport is `aria-label="Notifications (F8)"` (Radix default).

**Pitfall — e2e serves the built bundle, not source.** `start:mocks` (`NODE_ENV=production tsx .`)
serves `build/client`, so `app/**` edits need `npm run build` before they show up.
`reuseExistingServer: true` reuses whatever is already on the port — run on a fresh
`PORT` to avoid a stale dev server (its `tsx watch --ignore app/**` won't reload `app/**`).
Playwright launch args include `--autoplay-policy=no-user-gesture-required`, so the
"Autoplay blocked" toast does NOT fire in e2e tests.

The install banner renders at z-30; the toast viewport is `z-100` with `pointer-events-none`,
but the toast card is `pointer-events-auto` and overlaps the player bar (z-50), so a visible
toast blocks `Open queue` and other right-side player controls.

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

### Pitfall: CSS z-index overlays blocking clicks — DO NOT work around with page.evaluate

When a CSS layer (e.g. a `fixed inset-0 z-52` search overlay) sits above a target element at a lower z-index and blocks a click, the correct fix is **not** to bypass z-index with `page.evaluate`. The overlay is there for a reason — it covers the element intentionally. A `page.evaluate` click hack is a symptom that the test is trying to verify something it shouldn't.

**Rule:** If an overlay blocks your click, the test is testing the wrong thing. Remove the blocked assertion, don't work around it.

```ts
// ❌ WRONG — page.evaluate bypasses CSS layering to click a covered element.
//    If the test is called "clicking a track result plays the track,"
//    verifying the player bar shows the track title IS the test.
//    Opening the queue and checking the dialog is a different concern.
await page.evaluate(() => {
  const btn = document.querySelector('[aria-label="Open queue"]') as HTMLButtonElement;
  btn?.click();
});

// ✓ RIGHT — trim the test to its core assertion.
//    The player bar showing the track proves "playing from search" works.
const playerBar = await waitForPlayerBar(page);
await expect(playerBar.getByText("Search Play Track")).toBeVisible();
```

Real case: the search overlay (z-52) covered the player bar's "Open queue" button (z-50). Instead of working around it, the queue verification was removed — the test already proved the track plays by checking the player bar showed the track title. The queue checking was not what the test was supposed to verify.

### Pitfall: test.setTimeout(60_000) — don't use per-test timeouts

Do NOT add `test.setTimeout(60_000)` to every test. Playwright's default timeout (30s in CI) is already generous. If a test needs 60 seconds, the test is too slow — fix the test, not the timeout.

```ts
// ❌ WRONG — if every test needs this, the timeout isn't the problem
test("something", async ({ page }) => {
  test.setTimeout(60_000);
  // ...
});

// ✓ RIGHT — use the default timeout. If individual steps are slow,
//    add focused timeouts on the slow step, not the whole test.
```

### Pitfall: tests should test what they claim to test

A test named `"clicking a track result plays the track"` should verify that clicking a search result plays the track. It should NOT also verify queue dialog state, bottom nav visibility after closing sheets, or anything else. When a test breaks because an overlay covers an element, ask: "is this assertion actually what the test is supposed to verify?" If not, remove it.

### When fixing one test issue, audit the whole file

When a file has one broken test, the same pattern (excessive timeouts, wrong assertions, unnecessary interactions) often exists in other tests in the same file. After fixing the known issue, scan the entire file for:
- `test.setTimeout(60_000)` — remove
- `page.evaluate` workarounds for z-index — rewrite or remove
- Assertions that don't match the test name — trim to the core
