# Sentry Level Filtering

Both server and client Sentry configs use `beforeSend` to drop non-error events.
Only `error` and `fatal` levels reach Sentry; `warning` and `info` are silently dropped.

## Server (`server/utils/monitoring.ts`)

```ts
beforeSend(event, _hint) {
  // Only send events at error level or above
  if (event.level && event.level !== 'error' && event.level !== 'fatal') {
    return null
  }
  // Strip PII from error events
  const piiHook = createBeforeSendHook()
  return piiHook(event) as any
},
```

## Client (`app/utils/monitoring.client.tsx`)

```ts
beforeSend(event) {
  // Only send events at error level or above
  if (event.level && event.level !== 'error' && event.level !== 'fatal') {
    return null
  }
  // ... extension filter, etc.
},
```

## What gets through

- `Sentry.captureException(error)` — default level is `error` → ✅
- `Sentry.captureMessage(msg, { level: 'error' })` — explicit error → ✅
- `Sentry.captureMessage(msg, { level: 'warning' })` → 🗑️ dropped
- `Sentry.captureMessage(msg, { level: 'info' })` → 🗑️ dropped

## What does NOT get captured

- `console.error` — no `captureConsoleIntegration` configured. Console output and Sentry are separate channels.
