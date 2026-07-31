# Node.js 21+ `navigator.onLine` SSR Pitfall

**Date:** 2026-07-30 (updated 2026-07-31)
**Affected files:**
- `app/features/offline-app/is-offline-environment.ts`
- `app/hooks/use-online-status.ts` ← **the SSR-breaking one**

## Pattern

Any code that reads `navigator.onLine` and treats it as a boolean will break
on Node ≥21 where `navigator` exists but `onLine` is `undefined`.

The fix is always the same: add `typeof navigator.onLine === "boolean"` before
treating it as a boolean value.

## Affected locations (all 3 — fix all)

### 1. `isOfflineEnvironment()` — `is-offline-environment.ts`

```ts
// FIXED in PR #140
export function isOfflineEnvironment() {
  return (
    typeof navigator !== "undefined" &&
    typeof navigator.onLine === "boolean" &&
    !navigator.onLine
  );
}
```

### 2. `offlineClientMiddleware` server guard — `offline-client.middleware.client.ts`

```ts
// Added in PR #140 (defense-in-depth, but this code never runs during SSR —
// clientMiddleware is a CLIENT_NON_COMPONENT_EXPORT, not server middleware)
if (typeof document === "undefined") return next();
```

### 3. `readInitialOnlineStatus()` — `use-online-status.ts` ← **THE REAL SSR BUG**

```ts
// FIXED 2026-07-31
function readInitialOnlineStatus() {
  if (typeof navigator === "undefined") return true;
  if (typeof navigator.onLine !== "boolean") return true;  // ← added
  return navigator.onLine;
}
```

**This was the actual root cause.** `useState(undefined)` → `isOnline = false`
→ `OfflineStatusBanner` renders "You're offline. Showing downloaded music only."
during SSR. The banner rendered in the SSR HTML, and the page hydration froze
(on Node ≥21 in CI, Node 24).

## Why PR #140 didn't fix it

PR #140 fixed locations (1) and (2) but **never checked location (3)**.
`isOfflineEnvironment()` and `offlineClientMiddleware` are both
data-strategy/middleware layer code, neither of which runs during SSR on the
critical path (clientMiddleware is NOT server middleware). The actual SSR
breakage came from a React component's `useState` initializer reading
`navigator.onLine` without the boolean guard.

## Impact (before fix)

During SSR on Node ≥21:
- `OfflineStatusBanner` renders the offline banner in the initial HTML
- The banner includes "Downloads / Library / Playlists" nav instead of the
  full app shell
- Page `load` event never fires — hydration stalls
- User sees a broken page on reload

## Playwright SSR hydration test pattern

Add E2E tests that verify SSR output for logged-in users:

```ts
test("no offline UI in SSR after login + reload", async ({ page, login }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));

  await login();
  await page.goto("/", { timeout: 30000 });
  await page.reload({ timeout: 30000 });

  // Offline banner must NOT appear in SSR
  await expect(page.getByText("You're offline")).not.toBeAttached();

  // No SingleFetchNoResultError
  const hydrationErrors = errors.filter(e =>
    e.includes("No result found") || e.includes("SingleFetch")
  );
  expect(hydrationErrors).toEqual([]);
});
```

## Detection

```bash
node -e "console.log(typeof navigator !== 'undefined' && navigator.onLine !== true)"
# Node 21+: prints 'true' (BUG)
# Node 20-: prints 'false' (OK)
```
