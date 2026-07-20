# Express v5 Migration — Wildcard Routes

## The problem

Express v5 upgraded `path-to-regexp` from v0.1.x to v8.x. The new version **rejects bare `*` wildcards** — every wildcard must be a **named parameter**.

## Error signature

```
PathError [TypeError]: Missing parameter name at index N: /path/*
```

The server crashes at startup (exit code 1) with zero output because the error fires during route registration, before `app.listen()`.

## Diagnostic trap: tsx masks the crash

With `tsx` (TypeScript execution), the error may NOT appear on startup — the tsx path triggers route registration differently or lazily. The **esbuild-bundled production server** (`server-build/index.js`) always crashes. Always test both paths after upgrading Express.

## Fix: bare `*` → named `{*param}`

| Express v3/v4 (broken in v5) | Express v5 (fixed) |
|---|---|
| `app.get('*', ...)` | `app.get('/{*splat}', ...)` |
| `app.all('*', ...)` | `app.all('/{*splat}', ...)` |
| `app.get('/img/*', ...)` | `app.get('/img/{*imgPath}', ...)` |
| `app.get('/favicons/*', ...)` | `app.get('/favicons/{*favPath}', ...)` |
| `app.get(['/img/*', '/favicons/*'], ...)` | `app.get(['/img/{*imgPath}', '/favicons/{*favPath}'], ...)` |

The parameter name (`splat`, `imgPath`, `favPath`) is arbitrary — it's not used in these catch-all handlers, just required by the parser.

## Finding all occurrences

```bash
rg "\.(get|all|post|put|delete|use)\(\[?['\"][^'\"]*\*[^'\"]*['\"]" --include='*.ts' --include='*.tsx'
```
