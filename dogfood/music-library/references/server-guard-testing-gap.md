# Server Guard Testing Gap (offlineClientMiddleware)

The `typeof document === "undefined"` server guard in `offline-client.middleware.client.ts`
has **zero test coverage**. This is the most critical fix in the two-layer defense against
SSR corruption (`SingleFetchNoResultError`).

## Why it's untested

jsdom's `document` global uses property descriptors that `vi.unstubAllGlobals()` cannot
cleanly restore. Stubbing `document` as `undefined` leaks into subsequent tests in the
same file. The middleware test file explicitly acknowledges this:

```
// NOTE: we do NOT stub `document` to test the server guard because
// jsdom's `document` uses property descriptors that vi.unstubAllGlobals
// cannot restore, leaking `undefined` into subsequent tests.  The server
// guard is a trivial `typeof document === "undefined"` check —
// `isOfflineEnvironment` is tested separately for server environment
// correctness (see is-offline-environment.test.ts).
```

## What is tested

- `isOfflineEnvironment()` — `typeof navigator.onLine === "boolean"` guard tested for
  `undefined` (Node 22) and non-boolean values. ✅
- Middleware online path (jsdom: document exists, navigator.onLine is true). ✅
- Middleware offline path with stubbed `navigator.onLine = false`. ✅

## What is NOT tested

- **Server guard**: `typeof document === "undefined"` path in the middleware. ❌

## Risk

If the server guard has a bug (e.g., a typo, wrong condition, placement issue), it won't
be caught in CI. The SSR corruption would return. The `isOfflineEnvironment` boolean guard
is a partial defense, but the middleware calls `persistOfflineRootShell` and
`patchOfflineDataStrategyResults` — if either of those runs during SSR, it corrupts
hydration data regardless of `isOfflineEnvironment` returning false.

## Possible mitigation

Run a subset of middleware tests with `@vitest-environment node` instead of jsdom.
In Node environment, `document` is genuinely `undefined`, so the guard triggers naturally.
Caveat: `persistOfflineRootShell` and `resolveOfflineData` may also fail in Node
(localStorage, IndexedDB unavailable), so tests would need to stub those.
