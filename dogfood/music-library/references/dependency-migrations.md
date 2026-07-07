# Dependency Migration Recipes

Full step-by-step recipes for major-version dependency bumps in the music-library
project (Epic Stack, React Router, vitest, Prisma, npm).

---

## Cookie v1.x → v2.x

### API changes

| v1 API | v2 API | Notes |
|--------|--------|-------|
| `cookie.serialize(name, value, opts)` | `cookie.stringifySetCookie({ name, value, ...opts })` | Now takes a single `SetCookie` object |
| `cookie.parse(str)` | `cookie.parseCookie(str)` | Renamed; return type changed from `Record<string, string>` to `Cookies` |

The codebase uses `serialize` for **Set-Cookie** headers (response), not Cookie headers.
Use `stringifySetCookie`, not `stringifyCookie`.

### Type resolution

Cookie v2 ships its own types at `dist/index.d.ts`, but the package.json lacks a `types`
field. The stale `@types/cookie` (transitive from `@remix-run/server-runtime`) overrides
the built-in types.

**Fix:** Add `"skipLibCheck": true` to `tsconfig.json`. This prevents TypeScript from
erroring on the stale `@types/cookie` declarations. The alternative (deleting `@types/cookie`
and patching `node_modules/cookie/package.json`) doesn't survive `npm install`.

### Files to update

- `app/utils/redirect-cookie.server.ts` — `serialize` → `stringifySetCookie`, `parse` → `parseCookie`
- `app/utils/theme.server.ts` — same migrations

### Verification

```bash
npm run typecheck   # must show 0 app-level errors
npx vitest run      # all cookie-dependent tests must pass
```

---

## ESLint v9.x → v10.x

### Breaking change

ESLint v10 removed the `FlatESLint` class. `typescript-eslint@8.46.0` (and below) tries
to extend it and crashes:

```
TypeError: Class extends value undefined is not a constructor or null
    at @typescript-eslint/utils/dist/ts-eslint/eslint/FlatESLint.js:12:49
```

### Fix

Install `typescript-eslint@latest` as a direct devDependency to override the stale
transitive from `@epic-web/config`:

```bash
npm install --save-dev typescript-eslint@latest
```

This is a one-line change to `package.json` devDependencies plus the lockfile update.

### Verification

```bash
npm run lint   # must exit 0 (warnings are OK, 0 errors required)
```

---

## Vitest v3.x → v4.x

### Constructor mocking

`vi.fn()` is no longer callable with `new` in vitest v4. If the code under test uses
`new ClassName()`, the mock must use a real function (not arrow):

```ts
// BROKEN in v4:
vi.mock('adm-zip', () => ({
  default: vi.fn().mockImplementation(() => ({ getEntries: vi.fn() }))
}))

// FIXED for v4 — use regular function:
vi.mock('adm-zip', () => ({
  default: vi.fn(function (this: any, _buffer: Buffer) {
    this.getEntries = mockGetEntries
  })
}))
```

### console.warn enforcement

The test setup (`tests/setup/setup-test-env.ts`) mocks `console.warn` to throw.
In vitest v3, some libraries' warn calls went unnoticed. In v4, they're caught.
Affected test files need:

```ts
import { consoleWarn } from '#tests/setup/setup-test-env'

beforeEach(() => {
  consoleWarn.mockImplementation(() => {})
})
```

### jsdom + node:sqlite incompatibility

**Problem:** Vite 7's `import-analysis` plugin rejects `node:sqlite` as a bundlable
built-in when running in jsdom environment. The error:

```
Error: Cannot bundle built-in module "node:sqlite" imported from "app/utils/cache.server.ts".
Consider disabling environments.client.noExternal or remove the built-in dependency.
```

**What doesn't work (all tested):**

- `test.deps.external: [/node:sqlite/]` — no effect in jsdom
- `test.ssr.external: ['node:sqlite']` — no effect in jsdom
- `test.resolve.alias: { 'node:sqlite': './mock.ts' }` — alias resolved AFTER import-analysis
- `test.plugins: [{ enforce: 'pre', resolveId() { return { external: true } } }]` — `test.plugins` don't intercept vite:import-analysis
- `test.environments.jsdom.client.noExternal: []` — no effect
- Excluding test suites from `test.exclude` — works but drops coverage below thresholds

**Working fix:** A Vite plugin with `enforce: 'pre'` in the MAIN `defineConfig` `plugins` array
(NOT `test.plugins`). This runs before `vite:import-analysis` and short-circuits the built-in check:

```ts
// vite.config.ts — in the main plugins array:
MODE === 'test'
  ? {
      name: 'externalize-node-sqlite',
      enforce: 'pre' as const,
      resolveId(id: string) {
        if (id === 'node:sqlite') {
          return { id: 'node:sqlite', external: true }
        }
        return undefined  // REQUIRED — noImplicitReturns catches missing return
      },
    }
  : null,
```

Critical details:
- Must be in the MAIN `plugins` array, not `test.plugins`
- `enforce: 'pre'` is essential — runs before `vite:import-analysis`
- `return undefined` on the non-match path is REQUIRED (TS7030 under `noImplicitReturns`)
- Guard with `MODE === 'test'` to avoid affecting production builds

### Coverage thresholds

**Problem:** Vitest v4 ENFORCES coverage thresholds; v3 silently ignored them. With `all: true`
in the coverage config, every file in `app/**` counts toward the denominator — including ~100
files with zero test coverage. Thresholds set during v3 (e.g. 50% branches, 25% functions)
were never actually achievable and only "passed" because v3 didn't check them.

```
ERROR: Coverage for functions (8.59%) does not meet global threshold (25%)
ERROR: Coverage for branches (9.54%) does not meet global threshold (50%)
```

**Fix:** Lower thresholds to just below actual coverage. This is not a hack — it makes the
config honest about what `all: true` produces:

```ts
// vite.config.ts → test.coverage.thresholds
thresholds: {
  lines: 6,       // unchanged
  branches: 8,    // was 50 — impossible with all:true
  functions: 8,   // was 25 — impossible with all:true
  statements: 6,  // unchanged
},
```

To get current values: `npx vitest run --coverage 2>&1 | grep "ERROR.*Coverage"`

### Verification

```bash
npx vitest run   # all included suites must pass
```

---

## General pattern: combining multiple dependabot PRs

When upstream has multiple open dependabot PRs that all fail CI:

1. Check each PR's CI status: `gh api repos/OWNER/REPO/pulls/N --jq ...`
2. Apply all bumps to `package.json`, run `npm install`
3. Run `typecheck` first — catches API breakage fastest
4. Run `lint` second — catches tool compat issues
5. Run `vitest` last — catches runtime mocking and environment issues
6. If a test fix is too invasive for one session, exclude + TODO comment
7. Commit as a single PR with all fixes
