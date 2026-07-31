# SSR Hydration Testing Pattern

**When to use:** Debugging or guarding against SSR rendering issues (offline banner,
hydration mismatches, `SingleFetchNoResultError`) on Node ≥21, where `navigator.onLine`
is `undefined` during SSR.

## Single-route test template

```ts
import type { Page } from "@playwright/test";
import { test, expect } from "#tests/playwright-utils.ts";

test("no SSR hydration errors after login + reload", async ({ page, login }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (err: Error) => pageErrors.push(err.message));

  await login();
  await page.goto("/", { timeout: 30000, waitUntil: "load" });
  await page.reload({ timeout: 30000, waitUntil: "load" });
  await page.waitForTimeout(2000);

  // No SingleFetchNoResultError
  const hydrationErrors = pageErrors.filter(
    (e) => e.includes("No result found") || e.includes("SingleFetch")
  );
  expect(hydrationErrors).toEqual([]);

  // Offline banner must NOT appear in initial SSR HTML
  await expect(page.getByText("You're offline")).not.toBeAttached({ timeout: 5000 });
});
```

## Parameterized route smoke test

Covers all logged-in routes in one file. Each route gets its own isolated test
(runs in parallel, failures don't cascade):

```ts
import type { Page } from "@playwright/test";
import { test, expect } from "#tests/playwright-utils.ts";

const LOGGED_IN_ROUTES = [
  { path: "/", name: "home" },
  { path: "/library", name: "library" },
  { path: "/playlists", name: "playlists" },
  { path: "/search", name: "search" },
  { path: "/downloads", name: "downloads" },
];

// Shared helpers — use `Page` type, NOT `ReturnType<typeof test.info>["page"]`
function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (err: Error) => errors.push(err.message));
  return errors;
}

async function loginReloadAndCheck(page: Page, login: () => Promise<unknown>, path: string) {
  const errors = collectErrors(page);
  await login();
  await page.goto(path, { timeout: 30000, waitUntil: "load" });
  await page.reload({ timeout: 30000, waitUntil: "load" });
  await page.waitForTimeout(2000);

  // Core assertions
  await expect(page.getByText("You're offline")).not.toBeAttached({ timeout: 5000 });
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeAttached({ timeout: 5000 });

  const hydrationErrors = errors.filter(
    (e) => e.includes("No result found") || e.includes("SingleFetch")
  );
  expect(hydrationErrors).toEqual([]);
}

for (const { path, name } of LOGGED_IN_ROUTES) {
  test(`${name} (${path}) ok`, async ({ page, login }) => {
    await loginReloadAndCheck(page, login, path);
  });
}
```

## 404 error boundary SSR test

Verifies `OfflineAwareErrorBoundary` shows the real error page, not the offline fallback:

```ts
test("OfflineAwareErrorBoundary: real 404, not offline fallback", async ({ page, login }) => {
  const errors = collectErrors(page);
  await login();
  await page.goto("/nonexistent-ssr-test-404", { timeout: 30000, waitUntil: "load" });

  await expect(page.getByText("You're offline")).not.toBeAttached({ timeout: 5000 });
  await expect(page.getByText(/can't find this page|not found|404/i)).toBeAttached({ timeout: 5000 });

  const hydrationErrors = errors.filter(
    (e) => e.includes("No result found") || e.includes("SingleFetch")
  );
  expect(hydrationErrors).toEqual([]);
});
```

## Running

```bash
npm run dev:youtube-mocks
npx playwright test tests/e2e/ssr-hydration.test.ts --reporter=line
```

## Pitfalls

- **Playwright wants to start its own server.** If a dev server is already running,
  create a config override:
  ```ts
  // playwright.reuse.config.ts
  import baseConfig from "./playwright.config.ts";
  export default { ...baseConfig, webServer: { ...baseConfig.webServer, reuseExistingServer: true, command: "echo ok" } };
  ```
  Then: `npx playwright test --config=playwright.reuse.config.ts`

- **The `load` event may timeout** if hydration is broken. Use `waitUntil: "load"`
  with a generous timeout (30s) and `.catch()` to continue capturing snapshots.

- **Use `Page` type, not `test.info()`.** Writing shared helpers: `import type { Page } from "@playwright/test"`. `ReturnType<typeof test.info>["page"]` resolves to `TestInfo`, not the page fixture.

- **Snapshots on failure.** Playwright automatically saves an accessibility snapshot on failure that shows what SSR rendered.

## What to look for in a broken SSR snapshot

- "You're offline. Showing downloaded music only." → `useOnlineStatus` reading
  `navigator.onLine` as `undefined` during SSR
- Minimal navigation (Downloads / Library / Playlists only) → offline shell rendered
  instead of full app shell
- Missing navigation items (Home, Search) → partial render, hydration crashed
