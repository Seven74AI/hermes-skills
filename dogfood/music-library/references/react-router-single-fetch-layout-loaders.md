# React Router: `clientLoader.hydrate=true` on Parent Layouts (Anti-Pattern)

When a parent layout route (e.g. `root.tsx`) has `clientLoader.hydrate = true`,
React Router v8.2.0's `singleFetchLoaderNavigationStrategy` sets `foundOptOutRoute = true`.
This changes how ALL child routes' data is fetched in the single-fetch response.

**`clientLoader.hydrate = true` is designed for LEAF routes, not parent layouts.**
Putting it on `root.tsx` is an architectural mistake that cascades through the
entire route tree.

## Verified mechanism (React Router v8.2.0 source)

`single-fetch.js` lines 125-187, `singleFetchLoaderNavigationStrategy`:

1. For each matched route, `getRouteInfo(m)` returns `{ hasLoader, hasClientLoader }`
2. If a route has `hasClientLoader && hasLoader`: `foundOptOutRoute = true` (line 141)
3. Routes with only `hasLoader` (no `clientLoader`) are added to `routesParams` (line 158)
   and their data is resolved via `unwrapSingleFetchResult(await singleFetchDfd.promise, routeId)` (line 163)
4. The `singleFetchDfd` resolves to `fetchAndDecode(args, targetRoutes)` (line 178-179)
5. When `foundOptOutRoute = true` and `ssr = true`: `targetRoutes = [...routesParams.keys()]` (line 176)
   — only routes in `routesParams` are fetched
6. When `ssr = false` (client-side navigation): `targetRoutes = undefined` (all routes fetched)
7. During certain hydration/SSR paths, `singleFetchDfd` can resolve to `{ routes: {} }` (empty),
   causing `unwrapSingleFetchResult` to throw:

```
SingleFetchNoResultError: No result found for routeId "routes/music"
```

The error is thrown for ALL batched routes (all routes with server `loader` but no `clientLoader`).
Routes with `ErrorBoundary` exports silently catch it — in this codebase, `music.tsx`'s
`ErrorBoundary` renders `<OfflineAwareErrorBoundary />`, hiding the problem.

## CORRECT fix

**Replace `defineOfflineClientLoader("root")` with a plain `clientLoader` that does NOT set `hydrate=true`.**
The `hydrate=true` flag is what enters the `foundOptOutRoute` path; the `clientLoader` itself is needed
for offline support via `OFFLINE_ROUTE_POLICIES["root"]`.

**⚠️ Do NOT remove `clientLoader` entirely** — that breaks offline Playwright tests. Root's offline policy
is a "live" policy that expects a `clientLoader` to provide fallback data when `navigator.onLine` is false.
Without a `clientLoader`, root has no offline data and the page crashes.

```tsx
// ADD these imports to root.tsx:
import { isOfflineEnvironment } from "#app/features/offline-app/is-offline-environment.client.ts";
import { createFallbackOfflineRootShell, persistOfflineRootShell } from "#app/features/offline-app/offline-root-shell.client.ts";

// REPLACE the defineOfflineClientLoader export with:
export async function clientLoader({ serverLoader }: Route.ClientLoaderArgs) {
  if (isOfflineEnvironment()) {
    return createFallbackOfflineRootShell() as unknown as ServerLoaderData<typeof loader>;
  }
  const shell = (await serverLoader()) as unknown as OfflineRootShell;
  persistOfflineRootShell({
    user: shell.user,
    requestInfo: { ...shell.requestInfo, userPrefs: { theme: shell.requestInfo.userPrefs.theme ?? "light" } },
    ENV: shell.ENV,
  });
  return shell as unknown as ServerLoaderData<typeof loader>;
}

// REMOVE these imports from root.tsx:
// import { defineOfflineClientLoader } from "#app/features/offline-app/define-offline-client-loader.ts";
```

### Also remove offline redirect rules that block OAuth callback routes

In `offline-route-policies.client.ts`, remove the redirect entries for:
- `/music/services/youtube/auth`
- `/music/services/youtube/callback`

## Why other attempted fixes are WRONG

- **Adding clientLoaders to all child routes** (commit `5a972fb`): makes each route fetch individually
  instead of batching (N HTTP requests instead of 1). Doesn't fix the root cause (`foundOptOutRoute`
  is still `true`). Can still fail in certain hydration paths.

- **Removing `clientLoader` entirely from root** (PR #136): fixes `SingleFetchNoResultError` but
  **breaks offline Playwright tests**. Root's `OFFLINE_ROUTE_POLICIES["root"]` entry is a "live"
  policy that requires a `clientLoader` to provide fallback root shell data when `navigator.onLine`
  is false. Without it, offline navigation crashes because root data is missing and the middleware
  skips root (it's a live route).

## Verification

After applying the fix:
```bash
npx react-router typegen && npx tsc --noEmit
```

The `clientLoader` export should be gone from `root.tsx`. The `HydrateFallback`
export can remain (it's ignored without a `clientLoader`) or be removed.

## Offline redirect rules (additional pitfall)

`offline-route-policies.client.ts` line 98-102 had redirect rules that matched
`/music/services/youtube/auth` and `/music/services/youtube/callback`, redirecting
them to `/music/services` when offline. These break the OAuth callback flow and
should be removed regardless of the `clientLoader` fix.
