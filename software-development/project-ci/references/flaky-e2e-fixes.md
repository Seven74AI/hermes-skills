# Flaky Playwright E2E Test Fix Patterns

Recurring root causes and fixes for flaky Playwright E2E tests in CI, observed across shop, the-swarm, music-library, and other React Router + SQLite projects.

## Root Cause Categories

### 1. SQLite Busy Contention (Parallel Workers)

**Symptom:** Random `toBeVisible()` timeouts, `SQLITE_BUSY` errors in server logs.

**Cause:** Playwright runs tests with multiple workers (typically `--workers=4` on CI). Each worker has its own browser context, and the server serves all of them concurrently. When multiple tests hit the DB simultaneously (especially during `beforeEach` setup with `prisma.*.create()` or `afterEach` cleanup with `prisma.*.deleteMany()`), SQLite serializes writes — one wins, others get `SQLITE_BUSY` and the server returns 500.

**Fix:**
```typescript
// In app/utils/db.server.ts, after prisma client creation:
void client.$executeRaw`PRAGMA busy_timeout = 5000`
```
This makes SQLite wait up to 5s for the lock instead of failing immediately. The single most impactful fix for flaky SQLite-based E2E tests.

### 2. `networkidle` Hangs on Pages with Persistent Connections

**Symptom:** `waitForLoadState('networkidle')` times out after 30s, even though the page content is fully loaded. On CI, this causes ALL retries to fail (3/3) — the test is fundamentally broken, not flaky.

**Cause:** Some pages have long-lived connections that prevent the network from ever becoming truly idle:
- React dev-mode `<LiveReload>` or Vite HMR websocket (dev server)
- Stripe webhook polling (checkout pages)
- SSE event streams
- LiteFS replication monitoring
- MSW service worker lifecycle connections

`networkidle` waits for ZERO network connections for 500ms, which never happens on these pages.

**Fix:** Replace `networkidle` with `domcontentloaded`:
```typescript
// ❌ Hangs forever on pages with persistent connections (3/3 CI failures)
await page.waitForLoadState('networkidle')

// ✅ Waits for DOM ready, ignores background connections
await page.waitForLoadState('domcontentloaded')
```

For navigation after form submissions where you need to ensure the response arrived, use `waitForURL`:
```typescript
await submitButton.click()
await page.waitForURL('/account/**', { timeout: 15000 })
```

**Diagnosis:** If a test fails all 3 retries with the same timeout — look for `networkidle` in the test file. This is the #1 cause of "completely broken" tests in CI (pass locally, never pass in CI).

### 3. Toast/Flash Messages Race After Redirect

**Symptom:** `waitForURL()` succeeds (navigation complete) but `getByText(/email changed/i)` or similar toast text assertion fails. Happens on settings-profile, onboarding, and any page that uses session flash cookies for temporary messages.

**Cause:** The server sets a flash cookie before the redirect, then React Router reads it on the next page load to render a toast. `waitForURL` resolves when the URL changes, but the toast component may not have hydrated yet. The default 5s `toBeVisible()` timeout races React hydration.

**Fix:** Add explicit `waitForURL` BEFORE the toast assertion, with a longer timeout:
```typescript
// ❌ URL resolves but toast hasn't mounted yet
await submitButton.click()
await expect(page.getByText(/email changed/i)).toBeVisible()  // default 5s

// ✅ Wait for navigation, then assert with explicit timeout
await submitButton.click()
await page.waitForURL('/account/**', { timeout: 15000 })
await expect(page.getByText(/email changed/i)).toBeVisible({ timeout: 15000 })
```

### 4. Default `toBeVisible()` Timeout Too Short for CI

**Symptom:** `expect(locator).toBeVisible()` fails in CI but passes locally. Timeout: 5000ms.

**Cause:** Playwright's default `toBeVisible` timeout is 5 seconds. CI runners are slower (resource contention, cold caches, shared CPU) and page renders can take 8-12 seconds for pages with heavy Prisma queries or CSS transitions.

**Fix:** Explicitly set timeout on all `toBeVisible()` calls that follow navigation:
```typescript
// ❌ Default 5s — too short for CI
await expect(page.getByText(/email changed/i)).toBeVisible()

// ✅ Explicit 15s — handles CI slowness
await expect(page.getByText(/email changed/i)).toBeVisible({ timeout: 15000 })
```

Rule of thumb: every `toBeVisible()` call after a page navigation or form submission needs `{ timeout: 15000 }`.

### 5. Silent `.catch(() => {})` Swallows Failures

**Symptom:** Test proceeds after a failed `waitForLoadState` or `waitForURL`, then fails later with a confusing error — the real failure is invisible.

**Cause:** `.catch(() => {})` silently swallows the timeout error. The test continues with a partially loaded page and fails on the next assertion with no indication that the page wasn't ready.

**Fix:** Log a warning instead of silent swallow:
```typescript
// ❌ Silent failure — test proceeds blindly
await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})

// ✅ Logs a warning — visible in CI output, aids debugging
await page.waitForLoadState('networkidle', { timeout: 15000 })
  .catch((e: unknown) => console.warn('networkidle wait timed out, proceeding:', (e as Error).message))
```

### 6. a11y Color-Contrast on Admin Pages

**Symptom:** `expectPageToBeAccessible()` fails with color-contrast violations on admin pages using dark themes or custom color schemes.

**Cause:** Admin dashboards often use design systems with colored status badges (green/red/yellow), gradient backgrounds, or muted text — these routinely fail WCAG AA color-contrast rules. These are design choices, not accessibility bugs.

**Fix:** Disable `color-contrast` rule selectively for admin pages:
```typescript
await expectPageToBeAccessible(page, { disableRules: ['color-contrast'] })
```

### 7. CDP WebAuthn — `setUserVerified(false)` Does Not Trigger Server Rejection in Headless CI

**Symptom:** Passkey test "Failed passkey verification shows error" times out with `getByText(/failed to create passkey/i)` — 15s timeout, all 3 retries fail. The error message never appears.

**Cause:** CDP `WebAuthn.setUserVerified({ isUserVerified: false })` sets the virtual authenticator to report user-verification-failed, but in headless Chromium on CI, the WebAuthn flow doesn't propagate this correctly to the server. The server never receives the UV flag, so it accepts the passkey registration instead of rejecting it.

**Fix:** Skip this test in CI. It requires non-headless Chromium to correctly propagate UV flags:
```typescript
test('Failed passkey verification shows error', async ({ page, navigate, login }) => {
  test.skip(!!process.env.CI, 'WebAuthn.setUserVerified(false) does not trigger server rejection in headless CI Chromium')
  // ... test body
})
```

### 8. CDP WebAuthn Timing (General)

**Symptom:** Passkey tests fail intermittently — `WebAuthn.credentialAdded` event never fires, or `WebAuthn.credentialAsserted` times out.

**Cause:** Chrome DevTools Protocol (CDP) for WebAuthn virtual authenticators has timing sensitivity. The `client.once('WebAuthn.credentialAdded', ...)` promise races against the browser's WebAuthn flow. On slow CI, the browser may complete the ceremony before the CDP listener is registered.

**Fix:** Increase test timeout and add warm-up navigation:
```typescript
test.setTimeout(90_000)  // 90s instead of default 30s

// Warm up the browser with a fast page first
await page.goto('/')
await expect(page.getByLabel('User menu')).toBeVisible({ timeout: 15000 })
```

### 9. Shadcn/UI `role="checkbox"` Button — `.check()` Doesn't Work

**Symptom:** `page.getByLabel(/terms/i).check()` fails with `Clicking the checkbox did not change its state`.

**Cause:** Shadcn/ui checkboxes render as `<button role="checkbox">` not `<input type="checkbox">`. Playwright's `.check()` method verifies the element's `checked` property changed after clicking — but `<button>` elements don't have a `checked` property. The click fires, the visual state changes (via React), but the DOM property doesn't update.

**Fix:** Use `.click()` instead of `.check()` for shadcn checkboxes:
```typescript
// ❌ Fails on <button role="checkbox">
await page.getByLabel(/terms/i).check()

// ✅ Clicks the button — React handles state
await page.getByLabel(/terms/i).click()
await expect(page.getByLabel(/terms/i)).toBeChecked()  // verify via ARIA
```

## Diagnosing CI Failures Without Running Locally

Use `gh run view --log-failed` to extract failure details from a specific CI run:

```bash
gh run view <RUN_ID> --repo <owner/repo> --log-failed
```

This shows the exact Playwright errors, the test file + line number, and the retry count — all without needing to reproduce locally. Look for patterns:
- 3 retries all failing = fundamentally broken test (fix the logic or the environment)
- 1 retry failing but other 2 pass = true flaky (timeout/contention fix)
- All retries pass = was a one-time CI race (no code change needed)

### Using Git Branches to Fix Tests for an Already-Merged PR

**Symptom:** You push fixes to a branch but CI never runs. `gh pr view <number>` shows `state: MERGED` — the PR was auto-merged while you were working.

**Fix:**
```bash
# Check PR state first
gh pr view <number> --json state,headRefOid

# If merged, create a new branch from main
git checkout main && git pull origin main
git checkout -b fix/flaky-round2
git cherry-pick <your-commit>...
git push origin fix/flaky-round2
gh pr create --head fix/flaky-round2 --base main --title "fix: ..." --body-file /tmp/body.md
```

## Impact Assessment

When reducing failures from e.g. 34 → 16, distinguish:
- **True fixes:** Tests that now pass because of your changes (busy_timeout, domcontentloaded, timeout increase)
- **Shifted flakiness:** Tests that happen to pass this run but are still flaky (parallel execution order changed)

Always run CI at least 2-3 times after fixes. If a test passes 2/3 runs and fails 1/3, it's still flaky.

## Pitfalls

- **Don't fix flaky tests you can't reproduce.** If a test passes 10× locally, the issue is CI environment contention (CPU, disk I/O, network) — not the test code. Apply the environment fixes (busy_timeout, timeouts) rather than rewriting the test.
- **Don't increase timeouts blindly.** A test timing out at 15s was probably already broken at 5s — increasing to 30s just makes CI slower when it does fail. Fix the underlying issue first, then add a reasonable margin. The user will push back on blanket timeout increases — they want root-cause fixes, not bandaids.
- **`waitForTimeout(N)` (sleep) is NEVER the fix.** If a test needs a sleep, the real problem is a missing wait condition — use `waitForURL`, `waitForSelector`, `waitForResponse`, or a `toBeVisible` assertion with timeout instead.
- **Check if the PR is already merged before pushing follow-up fixes.** A kanban coder may have auto-merged the PR. Pushing to a merged PR's branch triggers no CI — you need a new PR from main.

- **Rebuild before running E2E locally after server code changes.** The `start:mocks` server imports from `build/server/` (the pre-built server bundle). If you change `app/utils/storage.server.ts` or any server-only code, run `npm run build` before `npx playwright test` — otherwise the E2E server runs the OLD compiled code and your fix appears to not work. CI handles this automatically (the build step runs before Playwright), but local runs don't.
