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

## Possible fixes (verified outcomes July 2026)

### ❌ Removing `HydrateFallback` from `root.tsx` — does NOT fix

Removing the export eliminates the `hydrateFallbackElement` but the error still
fires. After HydrateFallback removal, the error manifests on the **initial**
logged-out page load too, not just after login + reload. This confirms
`HydrateFallback` is a contributing factor but not the sole cause — the
underlying `routesParams.size === 0` shortcut fires regardless.

### ❌ Injecting `window.__reactRouterHdrActive = true` — does NOT fix

Adding `<script>window.__reactRouterHdrActive = true</script>` before
`<Scripts />` in `root.tsx`'s `<Document>` component places the flag in the
SSR HTML, but the error persists. Likely the flag is overwritten by React
Router's own initialization, or the timing is wrong (the data strategy runs
after the flag is cleared).

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
