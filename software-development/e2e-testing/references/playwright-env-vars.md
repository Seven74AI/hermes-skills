# Playwright E2E: Env Var Debugging Reference

## The Two-Environment Problem

Playwright E2E tests run with TWO separate process environments that must be kept in sync:

### Environment 1: Test Process
Set at the top of `playwright.config.ts` via `process.env`:
```ts
process.env.SESSION_SECRET = 'test-session-secret'
process.env.DATABASE_URL = `file:${BASE_DATABASE_PATH}`
// ... etc
```
This is where test fixtures (`login()`, `insertNewUser()`) run. They create users, sessions, and cookies using these env vars.

### Environment 2: webServer Subprocess
Set in the `webServer.env` config:
```ts
webServer: {
  env: {
    SESSION_SECRET: 'test-session-secret',
    DATABASE_URL: `file:${BASE_DATABASE_PATH}`,
    // ... etc
  },
}
```
This is the actual Express/Remix server that handles HTTP requests. It validates cookies, connects to the DB, and renders pages.

### The SESSION_SECRET Trap

`login()` creates a session cookie signed with `process.env.SESSION_SECRET`. The webServer verifies that cookie using `webServer.env.SESSION_SECRET`. If they differ, the cookie is rejected silently — the user appears logged out and the app redirects to `/login`.

This manifests as: the page snapshot shows the login form ("Welcome back!", "Username", "Password") instead of the expected authenticated page.

## Debugging Workflow

### Step 1: Read the Error Context

Every Playwright failure produces `test-results/<test-name>-retryN/error-context.md`. The `# Page snapshot` section is the single most valuable piece of data. It shows EXACTLY what Playwright's accessibility tree saw on the page.

| Snapshot shows | Meaning |
|---|---|
| `Internal Server Error` | Server crashed — check stderr for env validation errors |
| Login form ("Welcome back!") | `login()` failed — check `SESSION_SECRET` match |
| Vite `virtual:react-router/server-build` error | `NODE_ENV` mismatch — server started in Vite dev mode instead of production |
| Expected page content but missing element | The element genuinely isn't there — check the component code |

### Step 2: Run the Server Manually

```bash
cd project-root
npm run start:mocks > /tmp/stdout.log 2> /tmp/stderr.log &
sleep 10
curl -s http://localhost:3000/some-page | head -20
cat /tmp/stderr.log | grep "Invalid environment variables" -A 10
```

The stderr will show exactly which env vars are missing. Common pattern from `env.server.ts` with Zod validation:

```
❌ Invalid environment variables: {
  DATABASE_PATH: [ 'Required' ],
  SESSION_SECRET: [ 'Required' ],
  INTERNAL_COMMAND_TOKEN: [ 'Required' ],
  HONEYPOT_SECRET: [ 'Required' ]
}
```

### Step 3: Check env.server.ts for Required Vars

Projects with env validation (e.g., `app/utils/env.server.ts`) may have different requirements based on `NODE_ENV` and `MOCKS` flags. Common pattern:

```ts
const isMocksEnabled = process.env.MOCKS === 'true'
const isProduction = process.env.NODE_ENV === 'production'

return z.object({
  DATABASE_PATH: z.string(),                              // always required
  DATABASE_URL: z.string(),                               // always required
  SESSION_SECRET: isProduction ? z.string() : z.string().optional(),  // production-only
  INTERNAL_COMMAND_TOKEN: z.string(),                      // always required
  HONEYPOT_SECRET: z.string(),                             // always required
  CACHE_DATABASE_PATH: z.string(),                        // always required
  AWS_ACCESS_KEY_ID: isMocksEnabled ? z.string().optional() : z.string(),
  // ... etc
})
```

When `start:mocks` sets `NODE_ENV=production`, ALL vars become required.

### Step 4: Apply the Fix to BOTH Environments

```ts
// playwright.config.ts

import path from 'node:path'

const BASE_DATABASE_PATH = path.join(process.cwd(), './tests/prisma/base.db')

// === Environment 1: Test Process ===
process.env.DATABASE_URL = `file:${BASE_DATABASE_PATH}`
process.env.DATABASE_PATH = BASE_DATABASE_PATH
process.env.CACHE_DATABASE_PATH = path.join(process.cwd(), './tests/prisma/cache.db')
process.env.INTERNAL_COMMAND_TOKEN = 'test-internal-token'
process.env.HONEYPOT_SECRET = 'test-honeypot-secret'
process.env.SESSION_SECRET = 'test-session-secret'

import 'dotenv/config'

export default defineConfig({
  webServer: {
    // === Environment 2: webServer Subprocess ===
    env: {
      PORT: process.env.PORT || '3000',
      NODE_ENV: 'test',
      MOCKS: 'true',
      YOUTUBE_MOCKS: 'true',
      DATABASE_URL: `file:${BASE_DATABASE_PATH}`,
      DATABASE_PATH: BASE_DATABASE_PATH,
      CACHE_DATABASE_PATH: path.join(process.cwd(), './tests/prisma/cache.db'),
      INTERNAL_COMMAND_TOKEN: 'test-internal-token',
      HONEYPOT_SECRET: 'test-honeypot-secret',
      SESSION_SECRET: 'test-session-secret',  // MUST match process.env above
    },
  },
})
```

**Critical rule:** Every env var set in `webServer.env` must also be set in `process.env` (before `dotenv/config`) with the same value. `dotenv/config` won't override already-set vars, so `process.env` values take precedence and flow to both test fixtures and the webServer subprocess.

## Real-World Example: Music Library

The music-library project's `start:mocks` script:
```
"start:mocks": "cross-env NODE_ENV=production MOCKS=true tsx ."
```

Uses `NODE_ENV=production` which makes `SESSION_SECRET` required. The `.env` file only contains `DATABASE_URL`, `CACHE_DATABASE_PATH`, `LITEFS_DIR`, and `MOCKS` — none of the other required vars. Without the Playwright config providing them, every E2E test fails with "Internal Server Error".
