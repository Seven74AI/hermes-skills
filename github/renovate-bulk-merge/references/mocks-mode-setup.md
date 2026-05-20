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

```typescript
async function uploadToStorage(file: File | FileUpload, key: string) {
  // In mocks mode, skip actual upload
  if (process.env.MOCKS === 'true') return key
  // ... rest of upload logic
}
```

## What MOCKS does NOT fix

- **GitHub OAuth e2e**: `remix-auth-github` does server-side token exchange that MSW can't intercept. These tests only work in unit tests (MSW runs server-side via `setupServer`). Skip them in e2e with `test.skip()`.
- **MSW server-side calls**: MSW only intercepts browser-side requests. Any fetch() done in the server process (S3, Resend, GitHub API) needs its own mock logic in production code.
