# Express v5 Wildcard Route Migration

Express v5 upgraded path-to-regexp from v1 to v8. Bare `*` wildcards are no longer
valid — you must use named splat parameters.

## The fix

| Express v4 | Express v5 |
|------------|------------|
| `app.get('*', ...)` | `app.get('/{*splat}', ...)` |
| `app.all('*', ...)` | `app.all('/{*splat}', ...)` |
| `app.get(['/img/*', '/favicons/*'], ...)` | `app.get(['/img/{*imgPath}', '/favicons/{*favPath}'], ...)` |

## Detection

The error is silent in production builds. The bundled server (`server-build/index.js`)
exits with code 1 and produces NO output on stdout/stderr. Only visible in stderr:

```
PathError [TypeError]: Missing parameter name at index 6: /img/*
    at consumeUntil (path-to-regexp/dist/index.js:108:27)
```

- Dev mode (`tsx`, NODE_ENV=development) is unaffected (different code path).
- Prod mode (`node ./server-build/index.js`) crashes before `app.listen()` fires.
- The build step (`npm run build`) succeeds — the error is at runtime only.

## Full sweep

Search for ALL bare `*` in route patterns before merging Express v5:

```bash
rg "\.(get|all|post|put|delete|use)\(\[?['\"][^'\"]*\*[^'\"]*['\"]" --glob '*.ts'
```

## Real case (2026-07-14)

music-library PR #176 — Express v5 upgrade. CI passed typecheck + vitest + lint,
but Playwright E2E failed because `npm run start:mocks` (production server) crashed
on the `*` wildcards. Three routes affected:

- `app.get('*', ...)` — trailing slash redirect
- `app.all('*', ...)` — React Router handler
- `app.get(['/img/*', '/favicons/*'], ...)` — 404 for missing assets
