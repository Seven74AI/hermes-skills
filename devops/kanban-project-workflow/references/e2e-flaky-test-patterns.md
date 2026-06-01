# E2E Flaky Test Root-Cause Patterns

NOT timeout masks. Diagnose WHY the test fails, not just increase timeouts.

## Pattern 1: `networkidle` hangs forever on SSE/polling pages

**Symptom:** `waitForLoadState('networkidle')` times out (30s+) on pages with persistent
connections. CI retry count shows all attempts fail — test is fundamentally broken.

**Root cause:** Pages with LiveReload (dev mode), SSE, or polling connections never reach
idle state. `networkidle` waits for 500ms with zero network activity — impossible.

**Fix:** Replace with `domcontentloaded` or `waitForSelector`:
```typescript
// BROKEN — never resolves on SSE/polling pages
await page.waitForLoadState('networkidle')

// FIX — waits for DOM ready, then specific element
await page.waitForLoadState('domcontentloaded')
await expect(page.getByRole('heading', { name: /orders/i })).toBeVisible({ timeout: 15000 })
```

**Real case:** shop onboarding test (3/3 CI failures) — after filling form on page with
LiveReload, `networkidle` never resolved. Switched to `domcontentloaded` → 100% pass.

## Pattern 2: Shadcn checkboxes break `page.check()`

**Symptom:** `locator.check: Clicking the checkbox did not change its state` on
`getByLabel(/terms/i).check()`.

**Root cause:** Shadcn/ui checkboxes render as `<button role="checkbox">` not
`<input type="checkbox">`. Playwright's `check()` method verifies the element's
`checked` property changed — buttons don't have that property.

**Fix:** Use `.click()` instead of `.check()`:
```typescript
// BROKEN — shadcn checkbox is <button>, not <input>
await page.getByLabel(/terms/i).check()

// FIX — click the button directly
await page.getByLabel(/terms/i).click()
```

## Pattern 3: CDP WebAuthn `setUserVerified(false)` no-op in headless CI

**Symptom:** Passkey test expects error message "failed to create passkey" but it never
appears — 15s timeout × 3 retries all fail.

**Root cause:** CDP `WebAuthn.setUserVerified({ isUserVerified: false })` does not trigger
server-side rejection in headless Chromium. The browser's WebAuthn flow still succeeds.

**Fix:** Skip the test in CI — it can't pass in headless mode:
```typescript
test('Failed passkey verification shows error', async ({ page, navigate, login }) => {
  test.skip(!!process.env.CI, 'WebAuthn.setUserVerified(false) not supported in headless CI')
  // ... rest of test
})
```

The positive test (register and use passkeys) works fine. Only the negative case
(user verification failure) is affected.

## Pattern 4: Toast assertions race React hydration after redirect

**Symptom:** `toBeVisible()` fails on toast message AFTER `waitForURL()` succeeded.
URL changed but toast never appeared.

**Root cause:** Server-side actions set a flash cookie, redirect, then client-side
React hydration reads the cookie and renders the toast. The `waitForURL` resolves
when the navigation completes, but the toast component hasn't mounted yet.

**Fix:** Wait for URL first, then explicitly wait for the toast with generous timeout:
```typescript
// BROKEN — toast may not have mounted yet
await page.getByRole('button', { name: /submit/i }).click()
await expect(page.getByText(/email changed/i)).toBeVisible()

// FIX — wait for redirect first, then toast
await page.getByRole('button', { name: /submit/i }).click()
await page.waitForURL('/account/**', { timeout: 15000 })
await expect(page.getByText(/email changed/i)).toBeVisible({ timeout: 15000 })
```

## Pattern 5: SQLite busy from parallel workers

**Symptom:** Intermittent `SQLITE_BUSY` errors in E2E tests, especially with 4+ parallel
workers. Tests that create DB records sequentially get contention.

**Root cause:** Playwright runs 4 workers by default. Each worker's test creates/reads
records on the same SQLite database. No built-in retry.

**Fix:** Add PRAGMA busy_timeout in db.server.ts:
```typescript
void client.$executeRaw`PRAGMA busy_timeout = 5000`
```

This tells SQLite to wait 5s before failing — eliminates 80%+ of SQLITE_BUSY flakes.

## Anti-Patterns: What NOT to do

1. **Blanket timeout increases** — bumping `expect.timeout` from 5s to 15s masks
   real problems and slows CI. Fix the root cause, not the symptom.

2. **Silent `.catch(() => {})`** — swallowing `networkidle` failures hides the fact
   that the page never finished loading. Use `.catch((e) => console.warn(...))` to
   at least log the warning.

3. **Reducing workers** — going from 4 to 2 workers doubles CI time. The `busy_timeout`
   fix handles SQLITE_BUSY without slowing down the suite.
