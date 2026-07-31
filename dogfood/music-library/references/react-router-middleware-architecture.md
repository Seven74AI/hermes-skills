# React Router v7/v8 Middleware Architecture

**Date:** 2026-07-31

## Two separate middleware export slots

React Router v7/v8 has two completely independent middleware systems:

| Export | Runs on | Pipeline function | Route module field |
|---|---|---|---|
| `middleware` | Server (SSR) | `runServerMiddlewarePipeline` | `route.module.middleware` |
| `clientMiddleware` | Client (navigations) | `runClientMiddlewarePipeline` | `route.module.clientMiddleware` |

The Vite plugin defines them as separate export categories (from
`@react-router/dev/dist/vite.js`):

```js
const SERVER_ONLY_ROUTE_EXPORTS = [
    "loader", "action", "middleware", "headers"
];
const CLIENT_NON_COMPONENT_EXPORTS = [
    "clientAction", "clientLoader", "clientMiddleware", ...
];
```

They are NOT cross-mapped. A route exporting `clientMiddleware` does NOT
have its middleware execute during SSR. A route exporting `middleware` does
NOT have its middleware execute during client navigations.

## SSR middleware execution flow

During a document request (`handleDocumentRequest`):

```
staticHandler.query(request, {
  requestContext: loadContext,
  generateMiddlewareResponse: async (query) => { ... }
})
  → loadLazyMiddlewareForMatches(matches, manifest, mapRouteProperties)
    // loads lazy middleware from manifest — only `middleware`, not `clientMiddleware`
  → runServerMiddlewarePipeline({
      request, url, pattern, matches, params, context
    }, handler, errorHandler)
    → runMiddlewarePipeline(args, handler, ...)
      → matches.flatMap(m => m.route.middleware ? ... : [])
        // reads route.module.middleware — NOT route.module.clientMiddleware
      → callRouteMiddleware(args, middlewares, handler, ...)
```

**Key:** `runMiddlewarePipeline` reads `m.route.middleware` (line 1627 in
`index-react-server.js`), not `m.route.clientMiddleware`. The server data
routes are built by `createStaticHandlerDataRoutes` in `server-runtime/routes.js`,
where `middleware: route.module.middleware` (line 33) — the generic `middleware`
export, not `clientMiddleware`.

## Client middleware execution flow

During a client navigation (`getTurboStreamSingleFetchDataStrategy`):

```
defaultDataStrategyWithMiddleware(args)
  → if args.matches.some(m => m.route.middleware) → runClientMiddlewarePipeline(...)
    → runMiddlewarePipeline(args, handler, ...)
      → matches.flatMap(m => m.route.middleware ? ... : [])
```

On the client, `route.module.clientMiddleware` is mapped to `dataRoute.middleware`
in `routes.js` (dom/ssr) line 125: `middleware: routeModule.clientMiddleware`.

So the same field name (`middleware`) carries different content depending on
the build target — but the export names (`middleware` vs `clientMiddleware`)
never cross paths.

## Implication for offline middleware in Music Library

`root.tsx` exports:
```tsx
export const clientMiddleware: Route.ClientMiddlewareFunction[] = [offlineClientMiddleware];
```

There is no `middleware` export. Therefore:
- During SSR: `route.module.middleware` is `undefined` → no middleware executes
- During client navigations: `route.module.clientMiddleware` maps to
  `dataRoute.middleware` → `offlineClientMiddleware` executes normally

The `typeof document === "undefined"` guard in `offlineClientMiddleware` is
defense-in-depth — it protects against the possibility that a future React Router
version might change middleware execution, but today it targets a code path that
never runs on the server.

## Verification

Search the root route manifest to confirm no `middleware` export:
```bash
grep -r "export.*middleware" app/root.tsx
# Should only show "clientMiddleware", never a bare "middleware"
```
