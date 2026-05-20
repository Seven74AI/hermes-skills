# Prisma v7 + libsql Adapter — CI Debugging Session

## Environment

- **Project:** mnlamart/shop (e-commerce)
- **ORM:** Prisma 7.8.0 with `@prisma/adapter-libsql`
- **Database adapter:** `PrismaLibSql` wrapping `@libsql/client` → `better-sqlite3`
- **CI:** GitHub Actions, ubuntu-24.04, pnpm 10.33.4, Node 24
- **Test runner:** Playwright (29 failed, 7 flaky, 79 passed — all failures were `Operation has timed out` on Prisma queries)

## Error Signature

Every failing Playwright test:
```
PrismaClientKnownRequestError:
Invalid `prisma.category.create()` invocation:

Operation has timed out
```

All Prisma queries in the app server timeout, but `prisma migrate deploy/reset` (Prisma CLI, not adapter) succeed.

## Root Cause Chain

### 1. `packageManager: "pnpm@10"` — invalid version format

```json
// ❌ package.json
"packageManager": "pnpm@10"
```

pnpm requires exact versions (`pnpm@10.9.0`), not major-only. Every command emits:
```
WARN Cannot switch to pnpm@10: "10" is not a valid exact version
```

This is a warning, not fatal — but it causes constant noise and can confuse version detection.

### 2. `prisma.config.ts` ignores `package.json` seed config

Prisma v7 reads `prisma.config.ts` for all configuration. The `package.json` field:
```json
"prisma": { "seed": "tsx prisma/seed.ts" }
```
is silently ignored. Result: `prisma db seed` says "No seed command configured".

The `prisma migrate reset --force` step completes migrations but **never runs the seed script**. The database has schema but no data.

### 3. `better-sqlite3` in `allowBuilds` (transitive)

`@prisma/adapter-libsql` → `@libsql/client` → `better-sqlite3`. Only `better-sqlite3` needs to be in `allowBuilds` — the `@libsql/*` packages are prebuilt native modules with no build scripts.

```yaml
# pnpm-workspace.yaml
allowBuilds:
  better-sqlite3: true  # transitive dependency
```

### 4. Local vs CI behavior

- **Local (Node 22, pnpm 11):** `PrismaLibSql` works fine — creates, reads, deletes rows
- **CI (Node 24, pnpm 10):** `PrismaLibSql` times out on all queries
- **Prisma CLI:** Works in both environments (uses its own query engine, not libsql adapter)

The timeout in CI is suspected to be a combination of:
- Node 24 vs Node 22 native module compatibility
- Better-sqlite3 compilation differences on ubuntu-24.04 runner
- Possible libsql client version bug with file-based SQLite on Node 24

## Fixes Applied

1. `package.json`: `"packageManager": "pnpm@10"` → `"pnpm@10.9.0"`
2. `prisma.config.ts`: Added `migrations: { seed: 'tsx prisma/seed.ts' }`
3. `pnpm-workspace.yaml`: `better-sqlite3: true` already present (correct)

## Verification

Seed runs locally with PrismaLibSql:
```
🌱 Seeding...
👤 Created 5 users...: 1.286s
🐨 Created admin user "kody": 275.373ms
🛍️ Created product data...: 2.659s
📦 Created shipping data...: 70.813ms
🌱 Database has been seeded: 4.292s
```

All Prisma queries (create, upsert, delete, count) work correctly via PrismaLibSql adapter locally.
