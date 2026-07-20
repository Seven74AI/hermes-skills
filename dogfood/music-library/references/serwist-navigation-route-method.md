# Serwist NavigationRoute — method default

The Serwist `NavigationRoute` class registers under `method = "GET"` by default.
It does NOT intercept POST navigations. A POST `<Form method="post">` submission
will pass through to the network untouched.

## Source evidence (from `public/sw.js`, bundled Serwist 9.5.11)

### Route class constructor (line 1936)

```js
constructor(match, handler, method = "GET") {
```

The `method` parameter defaults to `"GET"`.

### NavigationRoute constructor (line 2094)

```js
constructor(handler, { allowlist = [/./], denylist = [] } = {}) {
  // ...
  super((options) => this._match(options), handler);
  // No 'method' arg → defaults to "GET"
}
```

Calls `super()` with only 2 args. No `method` passed → inherits the default `"GET"`.

### NavigationRoute._match (line 2120)

```js
_match({ url, request }) {
  if (request && request.mode !== "navigate") return false;
  // ...denylist/allowlist checks...
}
```

Only matches when `request.mode === "navigate"`. Does NOT check `request.method`.
If the route WERE registered for POST, it would match POST navigations.
But it's registered for GET only, so POST navigations never reach it.

### Router route lookup (line 2826)

```js
const routes = this._routes.get(request.method) || [];
```

Routes are stored and retrieved by `request.method`. POST requests look up
`this._routes.get("POST")` → won't find the `NavigationRoute` (stored under "GET").

### Router.registerRoute (line 2930)

```js
if (!this._routes.has(route.method)) this._routes.set(route.method, []);
this._routes.get(route.method).push(route);
```

Routes are bucketed by `route.method`. NavigationRoute's `method` is `"GET"`.

## Conclusion

When debugging a 405 on `<Form method="post">`, the Serwist service worker is NOT intercepting the request. The 405 comes from somewhere else — React Router, the Express server, or a middleware.
