---
name: sentry-monitoring
description: Set up Sentry error monitoring + performance tracing for React Router v7 / Epic Stack apps. Use when the user wants to add error tracking, performance monitoring, or session replay to a web app.
version: 1.0.0
---

# Sentry Monitoring Setup (React Router v7 / Epic Stack)

Wires up `@sentry/react-router` for error monitoring, performance tracing, and session replay in React Router v7 apps. Works with Epic Stack projects that already ship the Sentry packages but may not have them configured.

## Trigger

Use when the user wants to set up error monitoring, crash reporting, performance tracing, or Sentry for a web app — especially React Router v7 / Epic Stack projects.

## Prerequisites

- `@sentry/react-router` and `@sentry/profiling-node` already installed
- `SENTRY_DSN` set in deployment secrets (Fly.io, Vercel, etc.)
- Epic Stack vite config already has the `stripMonitoringWhenNoDSN()` plugin

## Implementation steps

### 1. Expose SENTRY_DSN to client ENV

In `app/utils/env.server.ts`, add to the `getEnv()` return:

```ts
SENTRY_DSN: process.env.SENTRY_DSN,
```

### 2. Server-side init: instrument file

Create `other/sentry/instrument.server.mjs`:

```js
import * as Sentry from '@sentry/react-router'
import { nodeProfilingIntegration } from '@sentry/profiling-node'

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  integrations: [nodeProfilingIntegration()],
  tracesSampleRate: 1.0,
  profilesSampleRate: 1.0,
  enableLogs: true,
})
```

### 3. Update start script

In `package.json`, add `--import` flag:

```json
"start": "cross-env NODE_ENV=production node --import=./other/sentry/instrument.server.mjs ."
```

### 4. Client-side init

In `app/entry.client.tsx`:

```tsx
import * as Sentry from '@sentry/react-router'

// Sentry client-side monitoring — stripped at build time when SENTRY_DSN is not set
if (ENV.MODE === 'production' && ENV.SENTRY_DSN) {
  Sentry.init({
    dsn: ENV.SENTRY_DSN,
    integrations: [
      Sentry.reactRouterTracingIntegration(),
      Sentry.replayIntegration(),
      Sentry.feedbackIntegration({ colorScheme: 'system' }),
    ],
    tracesSampleRate: 1.0,
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
  })
}
```

The `if (ENV.MODE === 'production' && ENV.SENTRY_DSN)` guard is critical — it matches the pattern that the Epic Stack `stripMonitoringWhenNoDSN()` plugin searches for. When `SENTRY_DSN` is not set at build time, the entire block is stripped from the production bundle, keeping the bundle size small (~182KB saved).

### 5. Server-side error handling

In `app/entry.server.tsx`, replace the plain `handleError` with Sentry's wrapper:

```tsx
import * as Sentry from '@sentry/react-router'

export const handleError = Sentry.createSentryHandleError({
  logErrors: false,
})

// Auto-instruments all server loaders, actions, middleware
export const instrumentations = [Sentry.createSentryServerInstrumentation()]
```

The `instrumentations` export provides automatic tracing for every loader, action, and middleware without per-route wrapping. Remove the old manual `handleError` function and its unused imports (`styleText`, `LoaderFunctionArgs`, `ActionFunctionArgs`).

### 6. Client-side error boundary capture

In `app/components/error-boundary.tsx`, add Sentry capture for unexpected errors:

```tsx
useEffect(() => {
  if (isResponse) return

  if (ENV.MODE === 'production' && ENV.SENTRY_DSN) {
    void import('@sentry/react-router').then((Sentry) => {
      Sentry.captureException(error)
    })
  }
}, [error, isResponse])
```

### 7. CSP update

In `app/utils/csp.server.ts`, add the Sentry ingest endpoint:

```ts
'connect-src': "'self' https://*.ingest.sentry.io",
```

## What's captured

| Source | Type |
|---|---|
| Client errors | React rendering crashes via `captureException()` in error boundary |
| Server errors | Loader/action/middleware exceptions via `createSentryHandleError()` |
| Performance | Transaction traces for every route load, loader, and action |
| Profiling | Node.js CPU profiles via `@sentry/profiling-node` |
| Replay | Session replays (10% of sessions, 100% on error) |

## Pitfalls

- **`createSentryHandleRequest` replaces the entire request handler** — it bypasses custom CSP headers, nonce injection, and Fly.io instance headers. Unless you need zero-config instrumentation, prefer keeping your custom `handleRequest` and using only `createSentryHandleError` + `instrumentations`.

- **The Epic Stack strip plugin is pattern-based** — it looks for literal `if (ENV.MODE === 'production' && ENV.SENTRY_DSN) { ... }` in specific files (`entry.client.tsx`, `error-boundary.tsx`). Any deviation from this exact pattern (different variable names, different conditions) will prevent stripping and bloat the production bundle.

- **`--import` flag requires Node.js 22+** — it runs an ESM module before the main entry point. The file **must** have an `.mjs` extension.

- **Dynamic import in error boundary uses `void` not `await`** — the `useEffect` callback can't be async. Using `void import().then()` is the correct pattern; the `vite.config.ts` strip plugin matches the `if` block pattern.

- **CSP: `connect-src` must allow Sentry's host** — the DSN contains the host (e.g., `o123456.ingest.sentry.io`), but the wildcard `*.ingest.sentry.io` covers all organizations without leaking the key.
