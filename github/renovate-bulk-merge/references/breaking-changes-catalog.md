# Breaking Changes Catalog

Quick reference for common major version breaking changes and their fixes.

## Express 4→5

**Symptom**: Server crashes with `Missing parameter name at index N: *`

**Fix**: Replace all bare `*` wildcards in route definitions with named wildcards:
- `app.get('*', ...)` → `app.get('{*path}', ...)`
- `app.all('*', ...)` → `app.all('{*path}', ...)`
- `app.get(['/img/*', '/favicons/*'], ...)` → `app.get(['/img/{*path}', '/favicons/{*path}'], ...)`

## Prisma v6→v7

**Symptom**: `Prisma schema validation - The datasource property 'url' is no longer supported`

**Fix**:
1. Install adapter: `npm install @prisma/adapter-libsql`
2. Create `prisma.config.ts`
3. Remove `url` from schema datasource
4. Update `db.server.ts` with `PrismaLibSql` adapter
5. Remove `?connection_limit=1` from all DATABASE_URL values
6. Align DATABASE_URL with DATABASE_PATH (both must point to same file)
7. `prisma migrate reset --force` no longer supports `--skip-seed` flag
8. CI DB cache needs `-prisma7` suffix to invalidate old caches

## Vitest v3→v4

**Symptom**: `Cannot bundle built-in module "node:sqlite"`

**Fix** (ONLY working solution): Vite plugin `externalizeNodeBuiltins()` as first plugin. Config-only approaches (`test.server.deps.external`, `test.ssr.external`, `resolve.external`) do NOT work.

## Sentry v9→v10

**Fix**: `npm install @opentelemetry/instrumentation`

## Stripe v19→v22

**Fixes**: 
- `apiVersion: '2026-04-22.dahlia'` (in BOTH `app/utils/stripe.server.ts` AND `tests/mocks/stripe.ts`)
- `Session.PaymentStatus` (enum) → `Session['payment_status']` (indexed access on type)
- `SessionCreateParams` type path changed → cast `new Stripe().checkout.sessions.create(params as any)` in production, `createReturns.payload as any` in test mock

**Pitfall**: Always update test mock files alongside production code. Breaking changes in Stipe types affect `tests/mocks/stripe.ts` equally — missing the mock update causes type errors that only surface in `tsc --noEmit`, not at runtime.

## React Router v7 types

**Symptom**: Loader/action test args missing `url` and `pattern` properties (50+ files).

**Fix**: Add `url: new URL('http://localhost'), pattern: ''` to all `createRemixStub` loader/action calls in test files. For bulk fixing across many files:
```bash
# Add url+pattern to loader arg objects
find tests -name '*.test.*' -exec sed -i 's/request: new Request/url: new URL("http:\/\/localhost"), pattern: "", request: new Request/g' {} +
```
Then clean up: `sed -i 's/pattern: "",\s*pattern: "",/pattern: "",/g'` for any doubles.

## express-rate-limit v7→v8

**Symptom**: TypeScript errors on `keyGenerator` — v8 requires a custom `keyGenerator` if you're doing anything beyond the default IP extraction.

**Fix**: Import and use the built-in IP key generator:
```ts
import { rateLimit, ipKeyGenerator } from 'express-rate-limit'
// ...
rateLimit({
  keyGenerator: (req) => ipKeyGenerator(req.ip ?? ''),
  // ... rest of config
})
```
Note: `ipKeyGenerator` takes a raw `string` (the IP), not a `Request` object. Extract `req.ip` first.

## set-cookie-parser v2→v3

**Symptom**: `Property 'name' does not exist on type 'Cookie | Cookie[]'`

**Fix**: v3 `parseString()` returns `Cookie | Cookie[]` instead of `Cookie`. Cast to `any` in test code (not production) since these are test utilities:
```ts
// tests/utils.ts, tests/setup/custom-matchers.ts, etc.
const cookie = setCookieParser.parseString(response.headers.get('set-cookie') ?? '') as any
const sessionCookie = cookie.find((c: any) => c.name === '_session') as any
```
Files that typically need this fix: `tests/utils.ts`, `tests/setup/custom-matchers.ts`, and any `$username.test.tsx` route test files that parse cookies.

## @epic-web/config v1→v3

**Fix**: Keep at v1 if using ESLint. v3 removed `./eslint` export.
