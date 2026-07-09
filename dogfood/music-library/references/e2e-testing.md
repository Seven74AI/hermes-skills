# Running E2E tests locally

## Prerequisites

`.env` must include:
```
DATABASE_URL="file:./data/data.db"
CACHE_DATABASE_PATH="./data/cache.db"
LITEFS_DIR=/tmp          # ⚠️ Required — SSR crashes without it
SESSION_SECRET="..."
HONEYPOT_SECRET="..."
MOCKS=true
# ... other mock env vars
```

## Commands

```bash
# Full E2E suite
LITEFS_DIR=/tmp npx playwright test

# Specific test file
LITEFS_DIR=/tmp npx playwright test tests/e2e/playlists.test.ts --reporter=line

# Specific tests by name pattern
LITEFS_DIR=/tmp npx playwright test tests/e2e/playlists.test.ts --grep "does not show" --reporter=line

# With UI (debugging)  
LITEFS_DIR=/tmp npx playwright test --ui
```

## Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `LITEFS_DIR is not defined` | Missing env var | Add `LITEFS_DIR=/tmp` to `.env` or export |
| All requests return 500 | Dev server crashes on SSR startup | Usually missing env vars; check `.env` completeness |
| `Invalid environment variables` | Zod validation failure | Ensure all required env vars are set in `.env` |
| Tests pass but against error pages | `getInstanceInfoSync` crash before app init | Add `LITEFS_DIR` — false negatives |
