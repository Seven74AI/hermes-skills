# MOCKS Mode Setup for E2E Tests

When running e2e tests, the production server needs specific env vars to trigger mock paths.

## Required env vars

```bash
# All from .env:
set -a && source .env && set +a

# Critical mock triggers:
RESEND_API_KEY=""                                    # Empty → triggers mock email path
GITHUB_CLIENT_ID=MOCK_GITHUB_CLIENT_ID               # Starts with MOCK_ → triggers OAuth mock
PLAYWRIGHT_TEST_BASE_URL=http://localhost:3000       # Disables rate limiting
MOCKS=true                                           # Triggers mock paths in email + storage
```

## Server startup command

```bash
set -a && source .env && set +a
PLAYWRIGHT_TEST_BASE_URL=http://localhost:3000 NODE_ENV=production MOCKS=true \
  node ./server-build/index.js
```

## Code changes needed for MOCKS support

### email.server.ts — mock email sending

```typescript
// Replace:
if (!process.env.RESEND_API_KEY && !process.env.MOCKS) {
// With:
if (!process.env.RESEND_API_KEY || process.env.MOCKS === 'true') {
```

Also write fixtures so e2e tests can read sent emails:

```typescript
// In the mock branch, add:
const { default: fsExtra } = await import('fs-extra')
const fixturesDir = path.join(process.cwd(), 'tests', 'fixtures', 'email')
await fsExtra.ensureDir(fixturesDir)
await fsExtra.writeJSON(path.join(fixturesDir, `${email.to}.json`), email)
```

### storage.server.ts — mock S3/Tigris uploads

In `app/utils/storage.server.ts`, add a MOCKS guard at the top of `uploadFile()`:

```typescript
export async function uploadFile(params: {
  file: File | FileUpload | Buffer
  key: string
  contentType?: string
  metadata?: Record<string, string>
  timings?: Timings
  onProgress?: (progress: { loaded: number; total?: number }) => void
}): Promise<string> {
  const { file, key, contentType, metadata, onProgress } = params

  // When running in mocks mode (E2E tests), skip the actual upload entirely.
  // The test only verifies the redirect + DB record, not the file content.
  if (process.env.MOCKS === 'true') return key

  // ... rest of upload logic
}
```

This guard must appear BEFORE `isStorageConfigured()` and the local filesystem fallback — otherwise the local fallback path still tries to write files during CI runs, which can fail silently.

## What MOCKS does NOT fix

- **GitHub OAuth e2e**: `remix-auth-github` does server-side token exchange that MSW can't intercept. These tests only work in unit tests (MSW runs server-side via `setupServer`). Skip them in e2e with `test.skip()`.
- **MSW server-side calls**: MSW only intercepts browser-side requests. Any fetch() done in the server process (S3, Resend, GitHub API) needs its own mock logic in production code.

## Pitfall: Local E2E testing requires a rebuild

When running Playwright E2E tests locally with `CI=true`, the `webServer` command (`npm run start:mocks`) imports pre-built server code from `build/server/index.js`. Changes to source files (e.g., `app/utils/storage.server.ts`) are NOT picked up unless you rebuild first:

```bash
npm run build    # compile source changes into build/server/
CI=true npx playwright test tests/e2e/some-test.test.ts
```

Without the rebuild, the server uses stale code and tests fail with the old behavior. This is the #1 cause of "it works on CI but not locally" (or vice versa). In CI, `npm run build` runs before Playwright (see `deploy.yml`), so local runs must replicate that order.
