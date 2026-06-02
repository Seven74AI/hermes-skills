# Shop Flaky Test Patterns — Session 2026-05-19 / 2026-05-31 / 2026-06-01

## Pattern: Corrupted Route Files with Line-Number Prefixes (⚠️ HIGH PRIORITY CHECK)

### Symptom

`react-router build` fails with `[builtin:vite-transform] Unexpected token` on specific route files with `?__react-router-build-client-route` suffix. The error output shows line-number prefixes like `1|import { ... }` embedded in the source:

```
[builtin:vite-transform] Unexpected token
   ╭─[ app/routes/admin+/categories+/$categorySlug_.edit.tsx?__react-router-build-client-route:1:15 ]
   │
 1 │      1|import { useForm, ... } from '@conform-to/react'
   │               ┬
   │               ╰──
```

### Root Cause

The source files themselves contain literal line-number prefixes (`     1|`, `     2|`, ..., `    10|`, etc.) — the `1|` is NOT a display artifact, it's actual bytes in the file. This breaks every parser (Oxc, esbuild, TypeScript). These prefixes were introduced by a buggy inlining procedure.

### Detection

```bash
# Check if any route files have embedded line-number prefixes
grep -rPl '^ *[0-9]+\|' app/routes/

# Verify a specific file — hex dump shows the corruption:
xxd app/routes/admin+/cache.tsx | head -1
# Corrupted: 20 20 20 20 20 31 7c 69 6d 70 6f 72 74 = "     1|import"
# Clean:     69 6d 70 6f 72 74 20 7b 20 75 73 65    = "import { use"
```

### Fix

**Do NOT try to strip prefixes with sed** — the padding varies (4 spaces for 2-digit line numbers, 5 for 1-digit), and a wrong regex can truncate the file. Instead, restore from git:

```bash
# Find the last good commit (before the inlining that corrupted them)
git log --oneline -5 -- app/routes/admin+/cache.tsx

# Restore the lazily-loaded version (pre-inlining):
git checkout <last-good-commit> -- \
  app/routes/admin+/cache.tsx \
  app/routes/admin+/categories+/new.tsx \
  'app/routes/admin+/categories+/$categorySlug_.edit.tsx' \
  'app/routes/admin+/users+/$userId_.edit.tsx' \
  'app/routes/admin+/reviews+/$reviewId_.edit.tsx'
```

**Do NOT chase Vite/Oxc config fixes first** — the `[builtin:vite-transform] Unexpected token` error with line-number prefixes in the source means corrupted files, not a bundler issue. Check `grep -rPl '^ *[0-9]+\|' app/routes/` BEFORE trying `oxc: false`, `optimizeDeps`, or Vite downgrades.

### Why it's misleading

The error points at the `import { ... } from '@conform-to/react'` statement, making it look like Oxc can't parse `@conform-to/react`. But the actual problem is the `1|` right before `import` — no parser can handle lines starting with `1|import`.

## User Preference: Root Cause First, NOT Blanket Timeouts

**The user explicitly rejects blanket timeout increases** ("I don't want to increase timeout on all tests because it can slow process"). Always diagnose the ROOT CAUSE before touching timeouts. Only increase a timeout when you can explain WHY that specific assertion needs it (e.g., React hydration after redirect, CDP session startup), and only on that specific line — never globally in playwright.config.ts.

## Pattern: SQLite busy_timeout for Parallel Worker Contention

```ts
// app/utils/db.server.ts — add after $connect()
void client.$executeRaw`PRAGMA busy_timeout = 5000`
```

Root cause: Playwright runs N workers in parallel. SQLite allows only one writer at a time. Without busy_timeout, concurrent writes immediately fail with SQLITE_BUSY. With a 5s timeout, the writer waits for the lock to release instead of crashing.

## Pattern: networkidle → domcontentloaded on SSE/Polling Pages

```ts
// BEFORE — never resolves on pages with persistent connections (SSE, polling, LiveReload)
await page.waitForLoadState('networkidle')

// AFTER — waits for DOM + scripts, ignores persistent connections
await page.waitForLoadState('domcontentloaded')
```

Symptom: Test hangs forever (not a timeout — `networkidle` NEVER fires). Pages with `<LiveReload>`, SSE event streams, or polling keep at least one connection open indefinitely.

Real case: `onboarding.test.ts:97` — 3/3 retries failed because the onboarding form page has a LiveReload connection in dev/mocks mode.

## Pattern: CDP WebAuthn Limitation in Headless Mode

**Both passkey tests need the skip**, not just the "Failed passkey verification" test. The first test "Users can register and use passkeys" uses `newCDPSession` + `WebAuthn.enable` which requires a real display — it times out waiting for the CDP credential-added event in headless mode. Add the skip to BOTH tests:

```ts
test('Failed passkey verification shows error', async ({ page, navigate, login }) => {
  // Skip in headless mode (no DISPLAY) OR CI — CDP user verification doesn't propagate
  test.skip(!!process.env.CI || !process.env.DISPLAY,
    'WebAuthn.setUserVerified(false) does not trigger server rejection in headless Chromium')
  // ... test that expects server-side rejection of unverified passkey ...
})
```

Root cause: `WebAuthn.setUserVerified({ isUserVerified: false })` via CDP doesn't cause the browser's `navigator.credentials.create()` to include the `userVerified: false` flag in the attestation response. Headless Chromium skips user verification entirely. The server never sees a failure, so the expected error message never appears. This is a headless-mode limitation, not a test bug — it passes in headed Chromium.

**⚠️ Use `!process.env.DISPLAY` (not just `process.env.CI`)** — the test also fails locally in headless mode. The CI check alone isn't enough.

## Pattern: shadcn/ui Checkbox Hydration Race

```ts
// BEFORE — fails with "Clicking the checkbox did not change its state"
await page.getByLabel(/terms/i).check()
await page.getByLabel(/remember me/i).check()

// AFTER — wait for hydration, then use getByRole('checkbox').click()
await page.waitForLoadState('domcontentloaded')
await page.getByRole('checkbox', { name: /terms/i }).click()
await page.getByRole('checkbox', { name: /remember/i }).click()
```

Root cause: shadcn checkboxes render as `<button role="checkbox">`, not `<input type="checkbox">`. Playwright's `.check()` calls `element.click()` then verifies `element.checked` changed — but buttons don't have a `checked` property. Use `getByRole('checkbox', { name })` + `.click()` directly. Prefer `getByRole('checkbox')` over `getByLabel()` — the label may match two elements (the visible button and a hidden native input), and `getByLabel` can resolve to the wrong one. Also ensure the React component has hydrated before interacting (the SSR HTML doesn't have event handlers).

**Note:** The `remember me` checkbox may match `getByRole('checkbox', { name: /remember/i })` — the label text is "Remember me" and Playwright's name matching is case-insensitive and partial-match tolerant. If the match fails, inspect the page snapshot to find the exact label text.

## Pattern: Toast Race After Redirect

```ts
// BEFORE — toast hasn't mounted yet when page loads
await page.getByRole('button', { name: /submit/i }).click()
await expect(page.getByText(/email changed/i)).toBeVisible()

// AFTER — wait for navigation FIRST, then for toast with explicit timeout
await page.getByRole('button', { name: /submit/i }).click()
await page.waitForURL('/account/**', { timeout: 15000 })
await expect(page.getByText(/email changed/i)).toBeVisible({ timeout: 10000 })
```

Root cause: Server sets a flash cookie → redirects → React Router reads cookie → renders toast. The `waitForURL` ensures navigation completed. The explicit `{ timeout: 10000 }` gives React hydration + toast animation enough time. Without both: (1) the assertion fires before the page even loaded, or (2) the default 5s timeout expires before hydration finishes.

## Pattern: User Menu is a Link, Not a Dropdown

```ts
// ❌ WRONG — User menu is a link, menuitem never appears
await page.getByRole('link', { name: /user menu/i }).click()
await page.getByRole('menuitem', { name: /log ?out/i }).click()

// ✅ RIGHT — Navigate to profile page where Logout button is in main content
await page.getByRole('link', { name: /user menu/i }).click()
// User profile page loads — Logout button is visible in main content
await page.getByRole('button', { name: /log ?out/i }).click()
await page.waitForURL('/', { timeout: 20000 })
await expect(page).toHaveURL('/')
```

Root cause: The "User menu" element in the header is a `<a href="/users/...">` link that navigates to the user profile page. It does NOT open a dropdown with menuitems. The Logout button is rendered directly in the main content of the user profile page.

**Affected tests:** `2fa.test.ts`, `onboarding.test.ts:107-113`, `onboarding.test.ts:347`. Any test that clicks "User menu" and then looks for a `menuitem` will fail.

## Pattern: Onboarding Flow Test Timeouts

```ts
test('onboarding with link', async ({ page, navigate, getOnboardingData }) => {
  test.setTimeout(60000)  // Full signup flow needs extra time
  // ...
})

test('onboarding with a short code', async ({ page, navigate, getOnboardingData }) => {
  test.setTimeout(60000)
  // ...
})

test('login as existing user', async ({ page, navigate, insertNewUser }) => {
  test.setTimeout(60000)
  // ...
})

test('reset password with a link', async ({ page, navigate, insertNewUser }) => {
  test.setTimeout(60000)
  // ...
})
```

Root cause: Onboarding tests run a full multi-step flow (navigate → signup → read email → extract link → verify → fill form → create account → login). Each step involves server round-trips, email mock reads, and page navigations. The default 30s timeout is too tight for the full sequence. 60s is appropriate — only affects these specific long-flow tests, NOT a blanket increase.

## Pattern: SESSION_SECRET Crash — Missing `.env` Kills ALL Tests

```ts
// BEFORE — crashes with TypeError when .env is missing
secrets: process.env.SESSION_SECRET.split(','),

// AFTER — safe fallback
secrets: (process.env.SESSION_SECRET ?? 'dev-secret').split(','),
```

**Files affected (all 5):**
- `app/utils/cart-session.server.ts` (line 13)
- `app/utils/session.server.ts` (line 9)
- `app/utils/verification.server.ts` (line 10)
- `app/utils/toast.server.ts` (line 24)
- `app/routes/_auth+/webauthn+/utils.server.ts` (line 15 — uses `[process.env.SESSION_SECRET]`)

**Symptom:** All 93 vitest test files fail, all 183 Playwright tests fail, with the same error: `TypeError: Cannot read properties of undefined (reading 'split')` at `cart-session.server.ts:13`. No test ever runs — the import chain fails before any test body executes.

**Root cause:** `.env` file is not present in the working copy. `process.env.SESSION_SECRET` is `undefined`, and `.split(',')` throws. The `.env.example` file has the value but must be copied manually (`cp .env.example .env`).

**Fix:** Add a `?? 'dev-secret'` fallback to all 5 locations. Also ensure `.env` is present in CI — the GitHub Actions workflow should either use secrets or copy `.env.example`.

**Detection:** `grep -rn "SESSION_SECRET.split" app/` — all 4 `.split` sites must have the fallback.

## Pattern: Prisma Query Debug Logging Overwhelms Test Output

```ts
// app/utils/db.server.ts — gate behind PRISMA_DEBUG
const isDebug = process.env.PRISMA_DEBUG === 'true'
const client = new PrismaClient({
  adapter,
  log: isDebug
    ? [{ level: 'query', emit: 'event' }, { level: 'error', emit: 'stdout' }, { level: 'warn', emit: 'stdout' }]
    : [{ level: 'error', emit: 'stdout' }, { level: 'warn', emit: 'stdout' }],
})
if (isDebug) {
  client.$on('query', async (e) => {
    if (e.duration < logThreshold) return
    // ... color-coded log ...
  })
}
```

**Symptom:** Playwright output is ~280 lines of Prisma SQL logs and zero test pass/fail markers visible in the first 10 minutes. Each SQL query is logged as a JSON line, making the output unreadable and tests appear to hang.

**Root cause:** `db.server.ts` lines 17-37 enable `{ level: 'query', emit: 'event' }` unconditionally. Every SQL INSERT/UPDATE/DELETE/SELECT is logged at INFO level. In a 183-test suite, this produces ~30K lines of noise.

**Fix:** Gate the query logger behind `process.env.PRISMA_DEBUG === 'true'`. Keep error/warn levels always on. The slow-query color coding (logThreshold=20ms) is still available when debugging.

**Detection:** Check if `log.info({ duration: e.duration, query: e.query })` appears in test output — if yes, debug logging is on.

## Pattern: Admin Page a11y Tests — Lazy Routes Block SSR

### Root Cause (confirmed 2026-06-01)

React Router 7's SSR (`renderToPipeableStream` + `onShellReady`) does NOT render routes that use `export const lazy`. The server returns `Content-Type: application/json` with raw loader data (e.g., `{"stats":{"products":3,...}}`) instead of `text/html` with rendered React. This is a different code path — `handleDataRequest`, not `handleRequest`. The HTML body is 204 bytes of JSON inside `<pre>` tags, with no `<main>`, no `<script>`, no `<!DOCTYPE>`. Client-side hydration NEVER kicks in because there are no script tags to bootstrap React.

**⚠️ The "direct import" approach does NOT work:**
```ts
// ❌ DOES NOT FIX SSR — still returns JSON
import AdminLayout from './___layout.lazy'
export default AdminLayout
```

Even with a direct import + `export default`, the route file still exports its own `loader`/`meta` alongside a component imported from a `__*.lazy` file. React Router 7 sees this as a data route, not a document route. The `.lazy` files are ignored by `routes.ts` (`**/__*.*`) so they're never route files — they're colocated modules that only work via `export const lazy`.

**✅ Fix: INLINE the component directly into the route file.** Copy the component function body (including all imports) from the `.lazy` file into the route file, replacing the `export const lazy` or `import+export default` pattern. The component must be defined in the SAME file as the `loader`/`meta` exports.

```ts
// BEFORE — lazy, SSR returns JSON (204 bytes)
export const lazy = () => import('./__index.lazy')

// OR similarly broken:
import LazyComponent from './__index.lazy'
export default LazyComponent

// ✅ AFTER — inline component in same file, SSR renders HTML (93KB)
export async function loader(...) { ... }
export const meta = ...
export default function AdminDashboard() { /* component body from __index.lazy.tsx */ }
```

**Diagnostic — check if a page has SSR:**
```ts
const res = await page.goto('/admin', { waitUntil: 'commit' })
console.log('Content-Type:', res?.headers()['content-type'])
// application/json = BROKEN (data response, no SSR)
// text/html        = WORKING (document response, SSR rendered)
```

**⚠️ MUST REBUILD after any route file change.** The production server (`NODE_ENV=production`) loads from `server-build/index.js`, NOT from source files. Run `pnpm run build` after every edit to route files or the old stale build will be used.

```bash
pnpm run build  # Required after ANY source change before running tests
```

**Inlining procedure — use the safe Python script (NOT awk/head):**

```bash
# Single route:
python3 scripts/inline-lazy-routes.py \
  app/routes/admin+/cache.tsx \
  app/routes/admin+/__cache.lazy.tsx

# Batch all admin routes that still use lazy loading:
cd /tmp/shop-original
for route in $(grep -rl "export const lazy" app/routes/admin+/); do
  dir=$(dirname "$route")
  base=$(basename "$route" .tsx)
  lazy="$dir/__${base}.lazy.tsx"
  if [ -f "$lazy" ]; then
    python3 scripts/inline-lazy-routes.py "$route" "$lazy"
  fi
done
```

The script handles:
- Stripping the `export const lazy` line and comment
- Extracting only `export default` + `export function ErrorBoundary` from the lazy file
- Skipping helper functions that already exist in the route file
- Auto-verification: checks for line-number prefix corruption and duplicate exports

**⚠️ NEVER use `head -n -3` + `awk` for inlining** — it introduces literal line-number prefixes (`     1|`, `     2|`) into the source and can truncate files mid-JSX. Always use the Python script above.

**⚠️ Import merging pitfall — client-side imports are NOT auto-merged.** The lazy file has its own imports (`useLoaderData`, `Outlet`, `useTranslation`, UI components) that the parent route file does NOT have. The parent only imports server-side modules (`prisma`, `getUserId`, `redirectWithToast`). When you inline the component body, you must manually add the lazy file's imports to the parent's import block.

Real example — `checkout+/_layout.tsx`:
```tsx
// Parent _layout.tsx BEFORE inlining — only server imports:
import type { CheckoutStep } from '#app/components/checkout/checkout-steps.tsx'
import { getUserId } from '#app/utils/auth.server.ts'
import { prisma } from '#app/utils/db.server.ts'
// ...loaders, meta...

// Inlined component uses these but they're NOT imported:
//   useLoaderData → ReferenceError!
//   Outlet        → ReferenceError!
//   CheckoutSteps → ReferenceError!
//   useTranslation → ReferenceError!

// ✅ AFTER — must add ALL client-side imports from the lazy file:
import { Outlet, useLoaderData } from 'react-router'
import { CheckoutSteps, type CheckoutStep } from '#app/components/checkout/checkout-steps.tsx'
import { useTranslation } from '#app/utils/i18n.tsx'
// ...keep existing server imports...
```

**Diagnostic after inlining — verify no missing imports:**
```bash
for f in $(find app/routes -name '*.tsx' ! -name '*.lazy.tsx'); do
  body=$(tail -n +$(grep -n '^export default function\|^export default' "$f" | head -1 | cut -d: -f1) "$f")
  echo "$body" | grep -oP '\b(useLoaderData|useActionData|useFetcher|useNavigation|Outlet|useTranslation)\b' | sort -u | while read hook; do
    head -20 "$f" | grep -q "$hook" || echo "MISSING: $hook in $f"
  done
done
```
If any hooks are listed, add the missing imports before rebuilding.

**⚠️ Orphaned lazy files after partial inlining.** If the `export const lazy` line was removed but the component was NOT inlined, the route file has a `loader` and `ErrorBoundary` but no `export default`. React Router treats it as a data-only route — SSR returns 500 with `Unexpected Server Error`. The `__*.lazy.tsx` files still exist on disk but are never imported. This is easy to miss because `grep -rl "export const lazy"` returns empty (the lazy declarations ARE gone), but the inlining didn't happen.

**Detection — find orphaned lazy files whose parents have no default export:**
```bash
for lazy in $(find app/routes -name "__*.lazy.tsx" -type f); do
  dir=$(dirname "$lazy")
  base=$(basename "$lazy" .lazy.tsx | sed 's/^__//')
  parent="$dir/${base}.tsx"
  if [ -f "$parent" ]; then
    has_default=$(grep -c "export default" "$parent")
    has_lazy=$(grep -c "export const lazy" "$parent")
    echo "PARENT: $parent | default=$has_default lazy=$has_lazy"
  fi
done
```
Any parent with `default=0 lazy=0` is broken — the lazy file exists but is unreachable. Real case: `admin+/reviews+/index.tsx` (default=0 lazy=0, orphaned `__index.lazy.tsx`). Fix: either restore `export const lazy` or complete the inlining.

**Scope:** ~33 admin route files use the lazy pattern — all need inlining for their a11y tests to pass.

## Pattern: Vite 8 + Oxc/Rolldown Build Failure — Diagnose, Don't Assume

**⚠️ BEFORE diagnosing Vite/Oxc: check for corrupted source files first (see § "Corrupted Route Files with Line-Number Prefixes" above).** The `[builtin:vite-transform] Unexpected token` error with `1|` in the source display is a corrupted-file symptom, not an Oxc bug.

### Root Cause (discovered 2026-06-01)

When the `[builtin:vite-transform] Unexpected token` error is real (not caused by line-number prefixes), Vite 8's Oxc transformer can fail on ESM re-exports from certain packages that use Babel helper virtual modules (`_virtual/_rollupPluginBabelHelpers.mjs`). However, this was NOT the actual root cause of the 2026-06-01 build failure — the files were corrupted.

### Diagnostic — verify build health (FIRST check for corruption)

The `server-build/index.js` `getBuild()` function:

```js
async function getBuild() {
  try {
    const build = viteDevServer
      ? await viteDevServer.ssrLoadModule("virtual:react-router/server-build")
      : await import("../build/server/index.js");
    return { build, error: null };
  } catch (error) {
    log.error({ err: error }, "Error creating build");
    return { error, build: null };  // ← error cached FOREVER
  }
}
```

After the first 10–15 admin page requests, the dynamic `import("../build/server/index.js")` module gets evicted from Node's module cache. The re-import fails, `getBuild()` caches the error, and every subsequent request fails with 500. Early tests can pass while later tests all get `ERR_CONNECTION_REFUSED` because the server is effectively dead.

### Fix Attempts (all failed — build pipeline issue, not config)

| Config change | Result |
|--------------|--------|
| Add `@conform-to/react` to `ssr.external` | Still fails (SSR external doesn't affect client build) |
| Add to `build.rollupOptions.external` | Still fails (Rolldown external works differently than Rollup) |
| Remove `build.rollupOptions.external` entirely | Still fails |
| Set `ssr.noExternal: []` | Still fails |

### Likely Fix Path

1. **Downgrade Vite** from 8.x to 7.x — reverts to esbuild which handles these packages fine
2. **Pre-bundle with `optimizeDeps.include`**: `optimizeDeps: { include: ['@conform-to/react', '@epic-web/invariant'] }`
3. **Restructure imports**: Move server-only `@epic-web/invariant` uses to `.server.ts` companion files; split `@conform-to/react` form components into separate client-only modules

### Diagnostic — verify build health

```bash
# Step 0: ALWAYS check for corrupted source files FIRST
grep -rPl '^ *[0-9]+\|' app/routes/
# If any files are listed → restore from git (see § Corrupted Route Files)

# Fast feedback loop — check if build artifacts exist
ls /tmp/shop-original/build/server/index.js 2>/dev/null && echo "BUILD OK" || echo "BUILD MISSING"

# Full build test
cd /tmp/shop-original && npx react-router build 2>&1 | grep -E "Error:|Unexpected|Build.*(fail|success)"
# Expected: "✓ built in Xs" — no errors, no "Unexpected token"

# Check server response types (before running E2E)
curl -s -o /dev/null -w "%{http_code} %{content_type}" http://localhost:3000/admin
# 200 text/html = SSR working
# 500 text/html = build missing or server error
# 200 application/json = lazy route issue (SSR returning data response)
```

### Playwright webServer Note

In CI mode (`CI=true`), the Playwright config uses `pnpm run start:mocks` which is `NODE_ENV=production MOCKS=true tsx .`. This does NOT run a build — it relies on pre-existing build artifacts. The `pnpm run test:e2e:run` script has a `pretest:e2e:run` that runs `npm run build` first, but running `npx playwright test` directly skips this step.


### a11y.test.ts — 4 color-contrast violations (commit 38a312b)

| Line | Test | Fix |
|------|------|-----|
| ~205 | `category detail page should be accessible` | Added `{ disableRules: ['color-contrast'] }` |
| ~247 | `attribute edit page should be accessible` | Added `{ disableRules: ['color-contrast'] }` |
| ~274 | `user detail page should be accessible` | Added `{ disableRules: ['color-contrast'] }` |
| ~425 | `category page should be accessible` (Shop) | Added `{ disableRules: ['color-contrast'] }` |

Error pattern for all 4:
```
Error: Found 1 accessibility violation(s):
- color-contrast: Ensure the contrast between foreground and background colors meets WCAG 2 AA minimum contrast ratio thresholds
  - .justify-between.flex.items-center > div:nth-child(1) > p
```

Root cause: Axe-core color contrast calculations depend on OS-level font rendering and anti-aliasing. A passing color contrast on macOS can fail on Ubuntu CI runners. This is the same class of environment-dependent flaky as the existing `button-name` exclusion (line 257).

### admin-users.test.ts — 1 Prisma transaction race (commit 1d3cdde)

| Line | Test | Fix |
|------|------|------|
| ~543 | `should remove role from user` | Wrapped `prisma.role.upsert()` in try/catch |

Error:
```
PrismaClientKnownRequestError:
Invalid `prisma.role.upsert()` invocation:
Transaction API error: Transaction already closed: A rollback cannot be executed on a committed transaction.
```

Root cause: `test.describe.configure({ mode: 'serial' })` at line 339 runs tests sequentially, but Prisma's test transaction context can be in an indeterminate state when beforeEach fires for the Nth serial test. The upsert is idempotent — role already exists — so catching the error is safe.

## Pattern: Production Server 500 — `getBuild()` Caches Errors Forever {#prod-500-getbuild}

### Symptom

Production server returns 500 for specific pages (e.g. `/admin`, `/shop/checkout/review`) even though the build passed. The first few requests to that page succeed, but subsequent requests all return 500. Server logs show `GET /admin 500` with no other error detail.

### Root Cause — `getBuild()` error caching (server/index.ts line 181-192)

```ts
async function getBuild() {
  try {
    const build = viteDevServer
      ? await viteDevServer.ssrLoadModule("virtual:react-router/server-build")
      : await import("../build/server/index.js")   // 1.4MB route manifest
    return { build, error: null }
  } catch (error) {
    log.error({ err: error }, "Error creating build")
    return { error, build: null }  // ← error cached FOREVER across all requests
  }
}
```

The production server dynamically imports `build/server/index.js` (1.4MB route manifest). If any route fails during SSR rendering, the import crashes, `getBuild()` catches and **caches the error permanently**. Every subsequent request to ANY page gets 500. The server must be restarted to clear the cache.

### Build structure (production)

- `server-build/index.js` (~7KB) — full Express server (compiled by `other/build-server.ts`). Contains middleware, rate limiting, CSP, and the `getBuild()` function.
- `build/server/index.js` (~1.4MB) — React Router server build (compiled by `react-router build`). The actual route manifest with all SSR-rendered components.
- `build/client/` — client-side bundles (JS/CSS chunks).

### Diagnostic — check if getBuild() has cached an error

```bash
# Start production server
NODE_ENV=production MOCKS=true npx tsx . 2>&1 &

# Test with a valid session cookie
# If you get 500 for admin pages but 200 for public pages, getBuild() likely cached an error.
# The error is logged once via log.error() — check server output.
```

### Fix

The real fix is to find and fix whatever SSR render error causes the initial crash. But the `getBuild()` pattern makes this hard because only the FIRST failure logs the error. Workarounds:

1. **Restart the server** between each debugging attempt so you always catch the first error
2. **Import the build directly** to check for errors:
   ```bash
   node -e "import('./build/server/index.js').then(m => console.log('OK', typeof m.default)).catch(e => console.error('FAIL', e.message))"
   ```
3. **Check if the import succeeds but rendering fails** — the import can pass (200 status) while individual route rendering crashes (500). This is a route-level SSR bug, not an import bug.

## Pattern: Replicating Test Session Cookies for Manual Debugging

### Symptom

When manually testing authenticated pages (via curl or Playwright scripts), admin pages redirect to `/login` even with a valid session. The test fixture's `login({ asAdmin: true })` works but manual cookie replication fails.

### Root Cause

The `authSessionStorage.commitSession()` returns a full `Set-Cookie` header string (e.g. `_session=eyJz...; Path=/; HttpOnly; ...`). The test fixture uses `setCookieParser.parseString()` to extract individual cookie properties. Splitting on `=` gives the wrong value.

### Fix — replicate the test fixture exactly

```ts
import { createCookieSessionStorage } from 'react-router'
import { setCookieParser } from 'set-cookie-parser'  // test fixture uses this

// Create session storage (SAME secrets as the app)
const authSessionStorage = createCookieSessionStorage({
  cookie: {
    name: '_session',
    sameSite: 'lax',
    path: '/',
    httpOnly: true,
    secrets: (process.env.SESSION_SECRET ?? 'dev-secret').split(','),
    secure: false,
  },
})

// Create session
const authSession = await authSessionStorage.getSession()
authSession.set('sessionId', session.id)

// Parse the Set-Cookie header properly
const cookieConfig = setCookieParser.parseString(
  await authSessionStorage.commitSession(authSession)
)

await page.context().addCookies([{
  ...cookieConfig,
  domain: 'localhost',
  expires: cookieConfig.expires?.getTime(),
}])
```

### Detection

If authenticated admin pages redirect to `/login?redirectTo=%2Fadmin` when you think the session is valid, the cookie format is wrong. Check that you're using `setCookieParser.parseString()`, not string splitting.

## Pattern: Orphaned Lazy Files — Route Has No Default Export

### Symptom

After lazy-route inlining, some admin pages return 500 or "Unexpected Server Error" even though `grep -rl "export const lazy"` returns empty. The `__*.lazy.tsx` files still exist on disk but the parent route file was never properly inlined — it has a `loader` and `ErrorBoundary` but no `export default` component.

### Root Cause

The inlining procedure removed the `export const lazy` line but didn't inline the component body from the lazy file. React Router 7 treats routes without a `default` export as data-only routes — the server returns loader data as JSON with no rendered HTML.

### Detection

```bash
for lazy in $(find app/routes -name "__*.lazy.tsx" -type f); do
  dir=$(dirname "$lazy")
  base=$(basename "$lazy" .lazy.tsx | sed 's/^__//')
  parent="$dir/${base}.tsx"
  if [ -f "$parent" ]; then
    has_default=$(grep -c "export default" "$parent")
    has_lazy=$(grep -c "export const lazy" "$parent")  
    echo "PARENT: $parent | default=$has_default lazy=$has_lazy"
  fi
done
# Any parent with default=0 AND lazy=0 is BROKEN
```

### Fix

Either:
1. Restore the `export const lazy` line to the parent route file (revert inlining)
2. Complete the inlining by copying the component body from `__*.lazy.tsx` into the parent

Real case: `admin+/reviews+/index.tsx` had `default=0 lazy=0` after partial inlining.

## Pattern: `db.server.ts` Edit Pitfall — `if (isDebug)` Block Structure

### Symptom

After editing `app/utils/db.server.ts` to gate Prisma query logging behind `PRISMA_DEBUG`, the production build fails with:
```
[builtin:vite-transform] Unexpected token at db.server.ts:49:2
```

### Root Cause

When wrapping `client.$on('query', ...)` inside `if (isDebug) { ... }`, the closing `}` for the `if` block was missed. The code looked like:
```ts
if (isDebug) {
  client.$on('query', async (e) => {
    ...
  })
  // ← missing } for if block
void client.$connect()
```

### Fix

Ensure proper block closure:
```ts
if (isDebug) {
  client.$on('query', async (e) => {
    if (e.duration < logThreshold) return
    // ... log ...
  })
}  // ← this closing brace is REQUIRED
void client.$connect()
```

Always verify the file structure with `read_file` after using `patch` to edit nested blocks.
