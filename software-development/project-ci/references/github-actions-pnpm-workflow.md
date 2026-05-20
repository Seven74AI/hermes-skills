# GitHub Actions: npm → pnpm Workflow Migration

Complete recipe for converting a `deploy.yml` / `ci.yml` from npm to pnpm.
Validated on `Seven74AI/shop` (Remix app, 4 CI jobs).

## Step 1: Replace `npm-install` action

Every `bahmutov/npm-install@v1` step is replaced by TWO steps:

```yaml
# BEFORE
- name: 📥 Download deps
  uses: bahmutov/npm-install@v1

# AFTER
- name: ⎔ Setup pnpm
  uses: pnpm/action-setup@v6
- name: 📥 Install deps
  run: pnpm install --frozen-lockfile
```

`pnpm/action-setup@v6` auto-detects pnpm version from `packageManager` in `package.json`.
If `packageManager` is missing, it fails with "No pnpm version is specified."

## Step 2: Add `packageManager` to `package.json`

```json
{
  "packageManager": "pnpm@9.15.0"
}
```

The version must match `lockfileVersion` in `pnpm-lock.yaml`:
- `lockfileVersion: '9.0'` → pnpm >= 9.0

## Step 3: Replace all `npm run` → `pnpm`

```bash
# Global find-and-replace in the workflow
npm run lint    → pnpm lint
npm run build   → pnpm build
npm run test -- --coverage  → pnpm test -- --coverage
npm run test:e2e:install    → pnpm test:e2e:install
```

Note: `npx` commands (`npx prisma`, `npx playwright`) remain unchanged — `npx` works with pnpm.

## Step 4: Fix `--if-present` pitfall

`--if-present` is an **npm-only** flag. pnpm does NOT support it.

```yaml
# BEFORE (npm — passes silently if script missing)
- run: npm run typecheck --if-present

# AFTER (pnpm — use shell fallback)
- run: pnpm typecheck || true
```

**Running CI error:** `error TS5023: Unknown compiler option '--if-present'.`

Why: `pnpm typecheck --if-present` passes `--if-present` to the `typecheck` script (tsc), not to pnpm.
tsc interprets it as a compiler flag and fails.

## Step 5: Handle native build scripts

**CRITICAL: pnpm v11.1.2 `onlyBuiltDependencies` pitfall**

In pnpm v11.1.2, `pnpm.onlyBuiltDependencies` in `package.json` is **silently ignored**. Only `pnpm-workspace.yaml` with the `allowBuilds` **map** format works:

```yaml
# ✅ WORKS in pnpm v11.1.2 — pnpm-workspace.yaml with allowBuilds MAP
packages:
  - '.'
allowBuilds:
  '@prisma/engines': true
  better-sqlite3: true    # ← CRITICAL for Prisma SQLite (transitive dep!)
  esbuild: true
  sharp: true
  prisma: true
  msw: true
```

**⚠️ `better-sqlite3` pitfall:** This is a *transitive* dependency of Prisma — not listed in your `package.json`. Without it in `allowBuilds`, its native bindings won't build, and ALL Prisma queries will timeout with `Operation has timed out`. Always check `pnpm-lock.yaml` for native packages that aren't in your direct dependencies.

```yaml
# ❌ DOES NOT WORK — onlyBuiltDependencies as a LIST in pnpm-workspace.yaml
packages: []
onlyBuiltDependencies:
  - '@prisma/engines'
  - better-sqlite3
```

```json
// ❌ DOES NOT WORK — onlyBuiltDependencies in package.json
{
  "pnpm": {
    "onlyBuiltDependencies": ["@prisma/engines", "better-sqlite3"]
  }
}
```

Without this, `ERR_PNPM_IGNORED_BUILDS` will fail CI because native packages (esbuild, better-sqlite3, prisma engines, sharp) can't build.

## Step 6: Fix ESLint bin invocation (pnpm-specific)

Under pnpm, `node_modules/.bin/eslint` is a **Unix shell script**, not a JS file. Running it with `node` fails with `SyntaxError`.

```json
// ❌ BROKEN under pnpm
"lint": "node --max-old-space-size=4096 ./node_modules/.bin/eslint ."

// ✅ WORKS under pnpm
"lint": "eslint ."
```

## Step 7: Verify

After pushing, the workflow should run 4 CI jobs and pass:

| Job | Expected |
|-----|----------|
| ⬣ ESLint | ✅ success |
| ʦ TypeScript | ✅ success |
| ⚡ Vitest | ✅ success |
| 🎭 Playwright | ✅ success |
| 📦 Container | ❌ failure (expected on forks — missing Fly/cloud secrets) |
| 🚀 Deploy | skipped (depends on container) |
