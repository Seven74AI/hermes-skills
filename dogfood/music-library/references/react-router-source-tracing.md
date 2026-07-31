# Tracing React Router Internals from Source

When debugging a React Router SSR/hydration issue, do NOT rely on the minified
`node_modules/react-router/dist/` files alone. The built dist strips comments,
renames variables, and omits Vite-injected runtime files that are critical to
understanding the full behavior.

## Workflow

```bash
# 1. Clone the react-router repo (shallow, main branch)
git clone --depth 1 https://github.com/remix-run/react-router.git /tmp/rr-source

# 2. Search for the relevant symbol or error message
grep -r "HdrActive\|SingleFetchNoResult\|routesParams" /tmp/rr-source/packages/

# 3. Cross-reference the source with the built dist
# Source:  /tmp/rr-source/packages/react-router/lib/dom/ssr/single-fetch.tsx
# Dist:    node_modules/react-router/dist/production/lib/dom/ssr/single-fetch.js

# 4. Check BOTH the main lib AND the dev plugin packages
# The @react-router/dev Vite plugin injects runtime files that aren't in the lib dist:
grep -r "symbol_or_flag" /tmp/rr-source/packages/react-router-dev/
```

## Key insight: Vite-injected runtime files

`@react-router/dev`'s Vite plugin injects runtime JavaScript files during
`react-router dev` that are NOT present in production builds or in the
`react-router` npm package's `dist/`. These include:

- `packages/react-router-dev/vite/static/refresh-utils.mjs` — HMR refresh + revalidation
- `packages/react-router-dev/vite/static/rsc-refresh-utils.mjs` — RSC HMR variant

These files set flags like `window.__reactRouterHdrActive` that the core
library only **reads** but never **writes**. Checking only the lib source
gives an incomplete picture of the runtime behavior.

## Pitfall: minified dist analysis

The minified production dist in `node_modules/react-router/dist/production/`:
- Renames all local variables (router → `t`, matches → `e`, routesParams → `o`)
- Removes comments explaining intent
- Omits Vite-injected runtime files entirely

A grep of the dist for a symbol may find only **reads** of that symbol. Do not
conclude the symbol is "never set" without also checking the dev plugin source.
