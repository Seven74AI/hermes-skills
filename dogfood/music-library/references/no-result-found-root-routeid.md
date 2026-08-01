# "No result found for routeId 'root'" — Root Cause

**Error:** `No result found for routeId "root"` on page reload in production builds, **only when logged in**.

## Reproduction (verified July 2026)

```bash
# 1. Clean production build
cd ~/projects/music-library
npm run build

# 2. Start production server
NODE_ENV=production node index.js

# 3. Log in via agent-browser, then reload
agent-browser open http://localhost:3000/login --timeout 30000
agent-browser fill @e8 "kody"
agent-browser fill @e9 "kodylovesyou"
agent-browser click @e9 && agent-browser press Enter
sleep 3
agent-browser eval "location.reload()"
sleep 5
agent-browser console | grep "No result found"
# → No result found for routeId "root"
```

**Does NOT reproduce when logged out.** The error only fires on the logged-in
hydration path because the loader returns richer data (user object,
notifications) and the HydrateFallback path differs.

## Root cause: React Router 8.2.0 `HydrateFallback` + missing `__reactRouterHdrActive`

`root.tsx` exports `HydrateFallback` → React Router renders it during SSR
hydration. On the client side, `singleFetchLoaderNavigationStrategy` (line 174
of `single-fetch.js`) has this condition:

```js
if ((!router.state.initialized && router.state.navigation.state === "idle"
      || routesParams.size === 0)
    && !window.__reactRouterHdrActive)
    singleFetchDfd.resolve({ routes: {} });  // ← EMPTY routes
```

`window.__reactRouterHdrActive` is set ONLY in the **Vite HMR refresh utils**
(`refresh-utils.mjs:70-73` and `rsc-refresh-utils.mjs:28-31` in the
`@react-router/dev` package), injected by the Vite plugin during
`react-router dev`. It wraps HMR revalidations:

```js
// refresh-utils.mjs (injected by Vite plugin, dev-only, HMR-only)
window.__reactRouterHdrActive = true;
await __reactRouterDataRouter.revalidate();
// finally: window.__reactRouterHdrActive = false;
```

This means:
- **Initial page load (dev or prod):** `__reactRouterHdrActive` is `undefined` →
  `!window.__reactRouterHdrActive` is `true` — guard does not apply
- **HMR revalidation (dev only):** set to `true` →
  `!window.__reactRouterHdrActive` is `false` — guard blocks the empty-routes shortcut
- **Production builds:** the refresh-utils file is never injected → always `undefined`

The combination of `routesParams.size === 0` (all routes already have SSR-embedded
data, so they skip revalidation) + `!window.__reactRouterHdrActive` (always `true`
on initial load) resolves the deferred with `{ routes: {} }`, causing the error.

When `unwrapSingleFetchResult` later looks up `result.routes["root"]`, it's `null`
→ throws `SingleFetchNoResultError`.

### What the manifest says (verified from SSR output)

```json
"root": {
  "hasLoader": true,
  "hasClientLoader": false,
  "hasClientMiddleware": true
}
```

No `clientLoader.hydrate=true` anti-pattern here. The architecture (ADR-0015,
unified offline middleware) is correct.

### SSR response IS correct

The embedded stream includes `"root"` data — confirmed via curl. The error is
in the client-side revalidation, not server rendering.

Call site in minified code: `errorBoundaries-*.js:2:5707` — `k()` function
looks up `e.routes[routeId]`.

## Previous incorrect diagnosis

The "stale build artifacts" theory was wrong. The error reproduces on a
**completely clean** `npm run build` when logged in. A second rebuild does not
fix it — the bug is in React Router's runtime logic, not build output.

## Verified fix (July 2026) — committed as `7d54cbe`

### ✅ Two-layer fix: middleware (primary) + inline script (defense-in-depth)

The fix uses **two complementary layers**, both committed to the codebase:

**Layer 1 (primary):** Set `window.__reactRouterHdrActive = true` in
`offlineClientMiddleware`, right after the `typeof document === "undefined"`
server guard. This is the fix that actually prevents the error because
`clientMiddleware` wraps the data strategy: it runs as part of the
`runClientMiddleware` → `next()` → `singleFetchLoaderNavigationStrategy` chain,
so the flag is set immediately before React Router checks it.

```typescript
// In app/middleware/offline-client.middleware.client.ts
export const offlineClientMiddleware: MiddlewareFunction = async (
  { request },
  next,
) => {
  if (typeof document === "undefined") {
    return next(); // Server — pass through
  }

  // Guards against React Router 8.2.0 single-fetch empty-routes shortcut.
  // Without this, hydration on routes with HydrateFallback + embedded stream
  // data resolves singleFetchDfd with { routes: {} } instead of fetching.
  // Mirrors what the Vite HMR refresh-utils.mjs does in dev.
  window.__reactRouterHdrActive = true;

  // ... rest of middleware
};
```

**Layer 2 (defense-in-depth):** An inline `<script>` in `root.tsx`'s `<Document>`
component sets the flag before `<Scripts />`. This runs synchronously at HTML
parse time, before any module scripts load. It provides a belt-and-suspenders
layer — even if the middleware path is somehow bypassed, the flag is already set.

```tsx
// In app/root.tsx, inside <Document>, before <Scripts />:
<script
  nonce={nonce}
  dangerouslySetInnerHTML={{
    __html: `window.__reactRouterHdrActive = true`,
  }}
/>
<Scripts nonce={nonce} />
```

**Why the middleware layer is the primary fix:**

1. `runClientMiddleware` invokes our middleware
2. We set `window.__reactRouterHdrActive = true`
3. `next()` calls the actual `singleFetchLoaderNavigationStrategy`
4. Inside `he()`, `!window.__reactRouterHdrActive` is `false` → guard blocks
   the `{ routes: {} }` shortcut

The middleware approach mirrors what Vite HMR refresh utils do in dev. The
inline script alone was insufficient in earlier testing (stale build artifacts
or service worker caching may have been factors), but it serves as valid
defense-in-depth alongside the middleware fix.

**Verified via Playwright:** production build + login as `kody` / `kodylovesyou`
→ `/library` → reload → **0 errors, 0 routeId errors**, HydrateFallback preserved.

## Approaches confirmed NOT to work

### ❌ Removing `HydrateFallback` from `root.tsx` — does NOT fix

Removing the export eliminates the `hydrateFallbackElement` but the error still
fires. After HydrateFallback removal, the error manifests on the **initial**
logged-out page load too, not just after login + reload. This confirms
`HydrateFallback` is a contributing factor but not the sole cause — the
underlying `routesParams.size === 0` shortcut fires regardless.

### ❌ Inline HTML `<script>` only (without middleware) — insufficient alone

Adding `<script>window.__reactRouterHdrActive = true</script>` before
`<Scripts />` in `root.tsx`'s `<Document>` component places the flag in the
SSR HTML at parse time before React Router loads. Earlier testing showed this
alone was insufficient (possibly due to service worker caching or stale builds),
but it is committed alongside the middleware as a defense-in-depth layer.

### ❌ Clean rebuild — does NOT fix

The previous theory that "stale build artifacts" cause the error was wrong.
A completely clean `npm run build` with a fresh `node index.js` still
reproduces the error. The bug is in React Router's runtime logic, not in the
build output.

### Service worker pitfall

The service worker (Serwist) caches old build assets. After a rebuild, the
browser may still serve stale JS bundles from the SW cache, making it appear
as if a fix didn't work when in fact the new code was never loaded.

**Always unregister the SW before testing production builds:**

```js
// In agent-browser eval:
navigator.serviceWorker.getRegistrations().then(regs => {
  regs.forEach(r => r.unregister());
})
```

Or use agent-browser: `agent-browser eval "navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()))"`

## Playwright direct testing pattern (when Hermes browser is unavailable)

When the Hermes browser tool (agent-browser/Camofox) is unavailable,
Playwright can test production builds directly via `node -e` one-liners:

```bash
cd ~/projects/music-library && node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  // Navigate to login, fill form, submit
  await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
  await page.fill('#login-form-username', 'kody');
  await page.fill('#login-form-password', 'kodylovesyou');
  await page.evaluate(() => document.getElementById('login-form').requestSubmit());
  await page.waitForTimeout(3000);

  // Navigate to protected page
  await page.goto('http://localhost:3000/library', { waitUntil: 'networkidle' });

  // Critical test: reload while logged in
  errors.length = 0;
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  const fatal = errors.filter(e => e.includes('No result found for routeId'));
  console.log(fatal.length === 0 ? 'PASS' : 'FAIL: ' + fatal[0]);

  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
"
```

Key points:
- Use `page.evaluate(() => form.requestSubmit())` for React Router forms (not `.click()`)
- Honeypot field `from__confirm` has a preset encrypted value — don't clear it
- Add `waitUntil: 'networkidle'` to ensure hydration completes
- Collect errors via `page.on('pageerror')` — console errors are separate
