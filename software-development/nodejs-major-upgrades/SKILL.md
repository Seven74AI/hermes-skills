---
name: nodejs-major-upgrades
description: "Upgrade major versions of Node.js ecosystem packages (Express, Zod, etc.) and the Node.js runtime itself — breaking changes, migration patterns, CI verification."
version: 1.1.0
metadata:
  hermes:
    tags: [nodejs, upgrades, express, zod, breaking-changes, runtime]
---

# Node.js Major Upgrades

Upgrade major versions of Node.js runtime and ecosystem packages (Express, Zod, etc.) in a Node.js/TypeScript project.

## Node.js Runtime Upgrade (e.g., 22 → 24)

Triggered when the user asks to bump the Node.js runtime version. This is distinct from package upgrades — it changes the runtime itself across all surfaces.

### Audit first (before touching any files)

1. **Read the official migration guide:** `https://nodejs.org/en/blog/migrations/v<old>-to-v<new>` — lists all breaking changes, removed APIs, and codemods.
2. **Grep the codebase for deprecated/removed APIs:**
   - `util.is*()` methods (removed in 24)
   - `dirent.path` → `dirent.parentPath` (renamed)
   - `fs.truncate(fd)` → `fs.ftruncate(fd)` (removed in 24)
   - `tls.createSecurePair()` (removed in 24)
   - `Buffer` methods — check deprecation status
3. **Check `--import` flags** in `package.json` scripts (e.g., Sentry instrumentation). Node 24 tightened `--import` behavior — the hook file must be ESM (`.mjs`).
4. **Check native modules** — `better-sqlite3`, `sharp`, `esbuild`, `@sentry/profiling-node`. These need ABI-compatible prebuilt binaries for the new V8 version. Verify they support the target Node version.
5. **Check OpenSSL impact** — Node 24 ships OpenSSL 3.5 with security level 2 (rejects RSA/DSA < 2048 bits, ECC < 224 bits, RC4). External API calls using TLS may break.

### Files to change

Every surface that pins the Node version:

| Surface | Example |
|---------|---------|
| `package.json` engines | `"node": "22"` → `"24"` |
| `package-lock.json` | Regenerate with `npm install --package-lock-only` |
| `Dockerfile` | `FROM node:22-bookworm-slim` → `FROM node:24-bookworm-slim` |
| CI workflows (`deploy.yml`) | `node-version: 22` → `node-version: 24` (every job) |
| `.nvmrc` / `.node-version` | If they exist |

**Pitfall:** The lockfile embeds the `engines` field as-is. After changing `package.json`, run `npm install --package-lock-only` to regenerate it. A code review should grep for the old version in the lockfile to catch this.

### Rebuild native modules

After the version bump, native modules need to be rebuilt for the new V8 ABI:
```bash
npm rebuild
```
CI handles this automatically on `npm ci` — no extra step needed in the workflow.

### Verification

1. **CI pipeline must pass:** lint, typecheck, vitest, Playwright E2E (×2 shards if sharded), bundle-size
2. **Regenerated lockfile:** grep `package-lock.json` for the old version — should return 0 hits
3. **All surfaces match:** `package.json` engines = Dockerfile base image = CI `node-version`

## Node.js Runtime Upgrades (e.g., 22→24)

When upgrading the Node.js runtime itself, the workflow is different from package upgrades — native modules need ABI compatibility, deprecated APIs can break at runtime, and OpenSSL policy changes can block TLS connections.

### Pre-upgrade audit (before any file changes)

1. **Check for removed/deprecated API usage** in project source. Run codemods or grep for:
   - `util.is*()` — removed in Node 24, use native equivalents
   - `dirent.path` — renamed to `dirent.parentPath` (DEP0178)
   - `fs.truncate(fd, ...)` — use `fs.ftruncate(fd, ...)` (DEP0081)
   - `tls.createSecurePair()` — removed, use `tls.TLSSocket`
   - `crypto.generateKeyPair` options: `hash`→`hashAlgorithm`, `mgf1Hash`→`mgf1HashAlgorithm` (DEP0154)
2. **Check `--import` flags** in package.json scripts. Node 24 may tighten ESM hook requirements. If the hook is already `.mjs` (ESM), it should be fine.
3. **Check `@types/node` version** — should be ≥ the target Node version. If already ahead (e.g. `^26.x` when upgrading to 24), no change needed.
4. **List native modules** that need ABI compatibility: `better-sqlite3`, `sharp`, `esbuild`, `@sentry/profiling-node`, etc. These will be rebuilt by `npm rebuild` post-upgrade but verify they have prebuilt binaries for the target Node version.

### Files to change

- **`package.json`** — `engines.node` field
- **`package-lock.json`** — **MUST regenerate after engines change.** Run `npm install --package-lock-only`. CI will fail if the lockfile embeds the old Node version.
- **`Dockerfile`** — `FROM node:<old>-bookworm-slim` → `FROM node:<new>-bookworm-slim`
- **`.github/workflows/*.yml`** — `node-version` in `actions/setup-node` steps (use `replace_all` — there can be 5+ occurrences across jobs)
- **`.nvmrc` / `.node-version`** — if present

### Lockfile pitfall

After changing `engines` in `package.json`, `package-lock.json` still embeds the old engines value in its metadata. The code-review spec sub-agent caught this in PR #208. Always run `npm install --package-lock-only` and commit the regenerated lockfile.

### Verification

Same pipeline as package upgrades: typecheck → vitest → lint → build → server startup. Pay extra attention to:
- Playwright E2E tests (native browser launch, most sensitive to Node ABI changes)
- Production server startup (`npm run start:mocks`) — Sentry `--import` hooks and native profiling modules crash early

## Package Upgrades (Express, Zod, etc.)

Node runtime bumps are mostly config changes, not code changes. The pre-upgrade audit is the critical step.

### Pre-upgrade audit (codebase scan)

Before touching any files, scan for deprecated/removed APIs:

```bash
# Removed Node 24 APIs
grep -r "util\.is" --include="*.ts" --include="*.js" src/ | grep -v "util.inspect\|util.isDeepEqual"
grep -r "dirent\.path" --include="*.ts" --include="*.js" src/
grep -r "fs\.truncate(" --include="*.ts" --include="*.js" src/
grep -r "createSecurePair" --include="*.ts" --include="*.js" src/
```

Also check:
- `--import` hooks (e.g. Sentry instrumentation) — must be ESM `.mjs`. CJS hooks may break.
- `@types/node` version — should already be at or above the target version.
- Native modules: `better-sqlite3`, `sharp`, `esbuild`, `@sentry/profiling-node`, `prisma` — need rebuild. CI will catch failures.
- `fetch()`, TLS/HTTPS connections — OpenSSL 3.5 raises security level to 2. Weak certs (RSA < 2048-bit, RC4) are rejected at network level.

### Files to change

1. **`package.json`** — `engines.node`: `"22"` → `"24"`
2. **`package-lock.json`** — regenerate with `npm install --package-lock-only`
3. **`other/Dockerfile`** — `FROM node:22-bookworm-slim` → `FROM node:24-bookworm-slim`
4. **`.github/workflows/deploy.yml`** — `node-version: 22` → `24` (all jobs)
5. **`.nvmrc` / `.node-version`** — if they exist, bump them too

### Verification

CI pipeline (lint → typecheck → vitest → playwright → bundle-size) validates. No need for local smoke test unless native module concerns exist.

### Pitfalls

- **`pnpm-lock.yaml` vs `package-lock.json`**: If both exist, determine which package manager the project actually uses before regenerating lockfiles.
- **Extra files in commits**: Don't commit `.hermes/handoffs/` or other session artifacts. Check `git status` before committing.
- **Never trust `npm run dev` alone**: The production server (`node server-build/index.js`) may behave differently. CI's build step covers this.

## General workflow

1. `npm install <pkg>@latest` — install the new major version
2. `npm run typecheck` — catalog all type errors
3. Fix errors systematically, one category at a time
4. `npm run test -- --run` — verify all tests pass
5. `npm run build` — verify production build
6. `npm run lint` — verify linter passes
7. Test server startup in production mode (`npm run start:mocks` or equivalent)
8. Commit + push + open PR
9. Create kanban review ticket

## Node.js Runtime Upgrade (e.g. 22 → 24)

Upgrade the Node.js runtime version itself — distinct from package upgrades. Covers where version pins live and how to audit for breaking changes before bumping.

### Where version pins live (check ALL)

1. **`package.json`** — `engines.node` field
2. **`Dockerfile`** — `FROM node:<version>-bookworm-slim as base`
3. **CI workflow (`.github/workflows/*.yml`)** — `node-version:` in every job
4. **`.nvmrc` / `.node-version`** — if present (many projects lack these)
5. **`@types/node`** — devDependency, should match or exceed the runtime target

### Pre-upgrade compatibility audit

Before bumping any pins, scan the codebase for removed or renamed Node APIs. The most common ones across 22→24:

| API (removed/deprecated) | Replacement | Grep |
|---|---|---|
| `util.isArray()`, `util.isBuffer()`, etc. | `Array.isArray()`, `Buffer.isBuffer()`, etc. | `util\.is(?!Deep\|Inspect\|Native)` |
| `dirent.path` | `dirent.parentPath` | `dirent\.path[^N]` |
| `fs.truncate(fd, ...)` | `fs.ftruncate(fd, ...)` | `fs\.truncate\(` |
| `tls.createSecurePair()` | `new tls.TLSSocket()` | `createSecurePair` |
| `fs.F_OK`, `fs.R_OK` (top-level) | `fs.constants.F_OK`, `fs.constants.R_OK` | `fs\.F_OK\|fs\.R_OK\|fs\.W_OK\|fs\.X_OK` |

Also check:

- **`--import` flag** — Node 24 tightened ESM hook behavior. If the prod start script uses `node --import=./path/to/hook.mjs`, verify the hook is a valid ESM module.
- **Native modules** — `better-sqlite3`, `@img/sharp`, `esbuild`, `prisma` engines all have native components. Run `npm rebuild` after the Node upgrade. If a rebuild fails, the package may need a version bump.
- **OpenSSL 3.5** — security level raised to 2. External API calls (OAuth, Sentry, YouTube fetches) will fail if the remote server uses RSA keys < 2048 bits, ECC keys < 224 bits, or RC4 ciphers. This is an operational concern, not a code one — but if CI E2E tests hit external endpoints, they may break.

### Upgrade steps

1. Run the compatibility audit above — fix any deprecated API usage first
2. Install Node 24 locally: `nvm install 24 && nvm use 24`
3. `rm -rf node_modules && npm install` — fresh install with new Node
4. `npm rebuild` — rebuild native modules against Node 24
5. `npm run build` — verify production build works
6. `npm run typecheck` — catch any type-level regressions
7. `npm run test -- --run` — full unit test suite
8. Start the production server: `MOCKS=true NODE_ENV=production timeout 10 node ./server-build/index.js`
9. `npm run lint` — linter pass
10. Bump all version pins (engines, Dockerfile, CI workflow)
11. Commit + push + open PR
12. Let CI run the full pipeline (vitest, typecheck, lint, playwright shards)
13. Create kanban review ticket

### Pitfalls

- **Docker and CI must change together.** If you bump `engines` and Dockerfile but forget `node-version` in the CI workflow, CI still runs on the old Node version — your "passing CI" means nothing.
- **`@types/node` being ahead is fine, behind is not.** If `@types/node` is `^26.x` and you're targeting Node 24, that's fine — types are forward-compatible. If it's `^20.x` and you target Node 24, you may miss new API types.
- **`npm rebuild` is easy to forget.** Native modules compiled against Node 22 ABI will segfault on Node 24 without a rebuild. No error message — just crashes.
- **`npm run dev` with `tsx` can mask issues.** `tsx` uses its own loader — some Node version-specific behaviors only surface in the production `node` runtime. Always test the production server.

## Node.js Runtime Upgrades (e.g. 22 → 24)

Upgrading the Node.js runtime itself across a project. Triggered when the user asks to bump the Node version.

### Where Node version lives

Find every hardcoded reference before starting:
```bash
grep -rn 'node.*2[0-9]' --include='Dockerfile' --include='*.yml' --include='*.json' . ':!node_modules' ':!pnpm-lock.yaml'
```

Common locations:
- `package.json` → `"engines": {"node": "XX"}`
- `Dockerfile` → `FROM node:XX-bookworm-slim`
- `.github/workflows/*.yml` → `node-version: XX` (in every job)
- `.nvmrc` or `.node-version` (if present)

### Pre-upgrade audit

Before bumping, check for APIs deprecated/removed in the target version:
- `util.is*()` — removed in Node 24
- `dirent.path` → `dirent.parentPath` — renamed
- `fs.truncate(fd)` → `fs.ftruncate` — deprecated
- `tls.createSecurePair()` — removed
- `--import` flag — check Sentry/profiling hooks are ESM (`.mjs`)

### Native modules

After the version bump, native modules need ABI rebuilds. Key ones to verify:
- `better-sqlite3` — Prisma adapter
- `@sentry/profiling-node`
- `sharp` / `@img/sharp`
- `esbuild`

The CI pipeline (vitest + playwright) catches rebuild failures — no need for local smoke test if CI is trusted.

### OpenSSL changes

Node 24 ships OpenSSL 3.5 with security level 2. External API calls (YouTube OAuth, Sentry) may break if servers use weak TLS certs. This is an operational concern, not a code change.

### Steps

1. Audit (see above) — confirm no deprecated API usage
2. Bump `engines` in `package.json`
3. Bump `FROM node:XX` in Dockerfile
4. Bump every `node-version: XX` in CI workflow
5. Regenerate `package-lock.json`: `npm install --package-lock-only`
6. Commit + push + open PR on fork
7. CI validates: lint → typecheck → vitest → playwright → bundle-size
8. Merge, create consolidation PR to upstream

### Pitfalls

- `@types/node` may already be ahead of the runtime (e.g., `^26.1.1` on Node 22). No change needed.
- `package-lock.json` embeds the `engines` value from the last `npm install`. Regenerate it after bumping engines to avoid a stale reference.
- When the fork has branch protection on main, the consolidation PR to upstream must go through a separate branch (e.g., `consolidate/node-24`) rather than force-pushing main.
- After upstream merge, reset the fork: delete branch protection temporarily via API, force push to match upstream SHA, then restore protection. The PR-based sync path fails when fork and upstream have divergent squash-merge SHAs for the same logical change.

### Wildcard routes (`*` → named splat)

Express v5 upgrades `path-to-regexp` to v8, which requires **named** wildcard parameters. Bare `*` is rejected at route registration time with:
```
PathError [TypeError]: Missing parameter name at index <N>: *
```

**Fix:** Replace ALL bare `*` wildcards in route patterns:

```ts
// ❌ Before (Express v4)
app.get('*', handler)
app.all('*', handler)
app.get(['/img/*', '/favicons/*'], handler)

// ✅ After (Express v5)
app.get('/{*splat}', handler)
app.all('/{*splat}', handler)
app.get(['/img/{*imgPath}', '/favicons/{*favPath}'], handler)
```

**Pitfall:** The dev path (`tsx` + `NODE_ENV=development`) may appear to work because the route registration might not be evaluated eagerly. The production build (`esbuild`-bundled `server-build/index.js`) will crash silently with exit code 1. Always test the **bundled** production server, not just the dev server.

**Detection:** Run the production server directly:
```bash
MOCKS=true NODE_ENV=production PORT=3099 timeout 10 node ./server-build/index.js 2>/tmp/err.log
cat /tmp/err.log  # Look for "Missing parameter name at index"
```

### `@types/express`

Express v5 ships its own types. The existing `@types/express@^4` can stay installed — it doesn't conflict at runtime, but consider removing it if no other packages depend on it.

## Zod v3 → v4

### Import path changes

`@conform-to/zod` requires a different entrypoint for Zod v4:
```ts
// ❌ Before
import { parseWithZod } from '@conform-to/zod'

// ✅ After
import { parseWithZod } from '@conform-to/zod/v4'
```

Debug: even though `peerDependencies` says `"zod": "^3.21.0 || ^4.0.0"`, the default import only works with v3. The `/v4` entrypoint is the only supported path.

### Validation options rename

`required_error` → `error`:
```ts
// ❌ Before
z.string({ required_error: 'Username is required' })

// ✅ After
z.string({ error: 'Username is required' })
```

### ZodError structure

The error details property was renamed:
```ts
// ❌ Before
error.errors        // ZodError
error.errors[0]     // first issue

// ✅ After
error.issues        // ZodError
error.issues[0]     // first issue
```

### `z.function()` — no longer a schema

In Zod v4, `z.function()` is a "function factory", not a schema. It can't be used in `z.object()` or `z.union()`. Replace with `z.custom<Type>()` for type-level inference:

```ts
// ❌ Before
z.function().args(z.object({ loaderData: z.unknown() })).returns(z.custom<React.ReactNode>())

// ✅ After — define the type separately to avoid TSX ambiguity
type BreadcrumbFn = (arg: { loaderData: unknown }) => React.ReactNode
z.custom<BreadcrumbFn>()
```

**TSX pitfall:** In `.tsx` files, `z.custom<({ loaderData: unknown }) => React.ReactNode>()` triggers TS2842: `'unknown' is an unused renaming of 'loaderData'`. TypeScript interprets the destructured parameter as a rename, not a type annotation. Extract to a type alias.

### String format validators — top-level functions

```ts
// ❌ Before (deprecated, still works but prefer new form)
z.string().url()
z.string().email()
z.string().uuid()

// ✅ After
z.url()
z.email()
z.uuid()
```

**Note:** `z.uuid()` in v4 enforces RFC 4122 compliance (correct version/variant bits). Use `z.guid()` for backward-compatible UUID format validation.

### `superRefine` return type

`superRefine` callbacks must return `void | Promise<void>`, not `null`:
```ts
// ❌ Before
schema.superRefine(async (data, ctx) => {
  if (skip) return null           // ❌ Promise<null>
  if (invalid) {
    ctx.addIssue({...})
    return z.NEVER                // ❌ z.NEVER not void
  }
  return null                      // ❌
})

// ✅ After
schema.superRefine(async (data, ctx) => {
  if (skip) return                // ✅ void
  if (invalid) {
    ctx.addIssue({...})           // ✅ addIssue alone is sufficient
  }
  // no return needed              // ✅
})
```

### `z.record()` requires two arguments

```ts
// ❌ Before
z.record(z.string())

// ✅ After
z.record(z.string(), z.string())
```

## CI verification

After any major upgrade:

1. **Typecheck** — `npm run typecheck` must pass with 0 errors
2. **Unit tests** — `npm run test -- --run` must pass all tests
3. **Lint** — `npm run lint` must pass with 0 errors
4. **Build** — `npm run build` must produce a valid build
5. **Server startup** — The production server must start and respond:
   ```bash
   npm run build
   MOCKS=true NODE_ENV=production PORT=3099 timeout 10 node ./server-build/index.js
   # Must print: 🚀  We have liftoff!
   ```
6. **E2E tests** — Playwright CI must pass (not just the gate, the actual shards)

## Pitfalls

- **Never trust that `npm run typecheck` alone catches all breaking changes.** Runtime errors (like Express wildcard routes) only surface when the server actually starts. Always test the production server.
- **`npm run dev` is not sufficient verification.** The dev server often uses different code paths (Vite middleware, no bundling). Test the production build.
- **Bundle builds can mask errors differently than source.** esbuild preserves route strings verbatim but bundles imports. An error that's lazy in dev may be eager in the bundle.
- **CI Playwright failures with "webServer was not able to start" are almost always a server startup issue, not a test issue.** Check server logs, not test logs.
