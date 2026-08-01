# React Router 8: "No result found for routeId" on production hydration

## Symptom

```
Error: No result found for routeId "root"
```

Occurs **only in production** (`NODE_ENV=production`), **only after login + full‑page reload** (or any reload with a logged‑in session). Cold initial load (logged out) works fine. The error hash is in the built chunk name (e.g. `errorBoundaries-RB0Sz37l.js`).

The page renders the `HydrateFallback` indefinitely or crashes to a white screen.

## Root cause

React Router 8.2.0's `singleFetchLoaderNavigationStrategy` (in `single-fetch.ts`) has a guard:

```js
if (
  (!router.state.initialized && router.state.navigation.state === "idle" || routesParams.size === 0)
  && !window.__reactRouterHdrActive
) {
  singleFetchDfd.resolve({ routes: {} });
}
```

When all routes already have SSR data embedded in the HTML stream (as happens when logged in — the root loader returns user/notifications/requestInfo), `routesParams.size === 0` and the single-fetch promise resolves to `{ routes: {} }` instead of fetching from `/.data`. Then `unwrapSingleFetchResult` can't find `"root"` in the empty map and throws.

The `__reactRouterHdrActive` guard exists to prevent this during HMR-driven revalidations in dev (`refresh-utils.mjs`, `rsc-refresh-utils.mjs`), but is **never set on initial page load in production**. It's a dev-only mechanism that happens to also block the production bug when present.

## Diagnosis workflow

### 1. Confirm it's this bug

```bash
# Build and start production
npm run build
NODE_ENV=production node index.js &

# Check the HTML output
curl -s http://localhost:3000 | grep -o '"MODE":"production"'
# Should print: "MODE":"production"

# Check if SSR data contains root loader data
curl -s http://localhost:3000 | grep -o '"root"' 
# If "root" appears in the stream, the SSR data IS present — the client is dropping it
```

### 2. Reproduce the exact scenario

The bug triggers when routes already have SSR data, causing `routesParams.size === 0`. This happens:
- After login (root loader returns user object)
- On any page reload while authenticated
- With `HydrateFallback` exported (the fallback resolution triggers a revalidation)

Use Playwright to reproduce deterministically:

```js
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

page.on('pageerror', err => {
  if (err.message.includes('No result found for routeId')) {
    console.log('BUG REPRODUCED:', err.message);
  }
});

// Login
await page.goto('http://localhost:3000/login');
await page.fill('#login-form-username', 'user');
await page.fill('#login-form-password', 'pass');
await page.evaluate(() => document.getElementById('login-form').requestSubmit());
await page.waitForTimeout(3000);

// Critical: reload while logged in
await page.reload({ waitUntil: 'networkidle' });
```

### 3. Trace through the minified bundle

The error message `No result found for routeId` appears in the built `errorBoundaries-<hash>.js` chunk. Search for it to find the `unwrapSingleFetchResult` function, then work backward to `singleFetchLoaderNavigationStrategy`.

Alternatively, clone React Router source to read the TypeScript:
```bash
git clone https://github.com/remix-run/react-router.git /tmp/react-router
# Key files:
# packages/react-router/lib/dom/ssr/single-fetch.ts
# packages/react-router-dev/refresh-utils.mjs
```

### 4. Verify the guard gap

Check that `__reactRouterHdrActive` is NOT set in production HTML:

```bash
curl -s http://localhost:3000 | grep -c '__reactRouterHdrActive'
# 0 → bug will occur
# 1 → guard present (fix applied)
```

## Fix

Add **one line** in the root `clientMiddleware` (the function that runs during every data strategy execution):

```typescript
// app/middleware/offline-client.middleware.client.ts (or equivalent)
export const offlineClientMiddleware: MiddlewareFunction = async ({ request }, next) => {
  if (typeof document === "undefined") {
    return next(); // Server: pass through
  }

  // GUARD: Prevent React Router 8.2.0 single-fetch empty-routes shortcut
  window.__reactRouterHdrActive = true;

  // ... rest of offline/online logic
};
```

**Why this works:** React Router v8 runs `clientMiddleware` during SSR data strategy execution (see `getTurboStreamSingleFetchDataStrategy → args.runClientMiddleware`). By the time the single-fetch promise is evaluated, the guard is already set to `true`.

**Defense-in-depth:** Also add an inline script in the HTML shell (root.tsx Layout) that sets the flag before any module scripts load:

```tsx
<script dangerouslySetInnerHTML={{
  __html: 'window.__reactRouterHdrActive = true'
}} />
```

Place it **before** the React Router context injection script tags.

## What does NOT work

1. **Removing `HydrateFallback`** — The error persists because the root cause is the empty-routes shortcut, not the fallback itself. Removing the fallback changes the timing but doesn't prevent the shortcut.

2. **Inline script alone** (without middleware) — May work in some builds but is fragile. The middleware approach is more reliable because it runs inside the data strategy execution context.

3. **Service worker unregistration** — Not related. This is a React Router client-side logic issue, not a caching issue.

## TypeScript: Window type declaration required

TypeScript doesn't know about `window.__reactRouterHdrActive`. The CI typecheck will fail with:

```
error TS2339: Property '__reactRouterHdrActive' does not exist on type 'Window & typeof globalThis'.
```

Add a global declaration in the middleware file:

```typescript
declare global {
  interface Window {
    __reactRouterHdrActive?: boolean;
  }
}
```

This is required because `__reactRouterHdrActive` is not a standard DOM property — it's a React Router internal that's only declared in Vite HMR utility files (not exposed to consumer code). The optional `?` is correct: the flag is not guaranteed to exist on the Window at startup.

## Related

- React Router source: `singleFetchLoaderNavigationStrategy` in `single-fetch.ts`
- HMR guard utilities: `refresh-utils.mjs`, `rsc-refresh-utils.mjs` (dev-only)
- The `__reactRouterHdrActive` flag name stands for "HDR Active" (Hydrate/Dehydrate/Revalidate)
