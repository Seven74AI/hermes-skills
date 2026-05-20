# npm → pnpm Migration Pattern

Repeatable protocol for migrating a Node.js project from npm to pnpm. Validated on the shop project (16% disk savings on node_modules, 35% lighter lockfile).

## Baseline (before migration)

```bash
du -sh node_modules/
time npm install 2>&1 | tail -3
wc -c package-lock.json
time npm run build 2>&1 | tail -3
time npx vitest run 2>&1 | tail -5
```

## Migration steps

```bash
# 1. Install pnpm
npm install -g pnpm

# 2. Generate pnpm-lock.yaml (npm→pnpm conversion)
pnpm import

# 3. Backup npm artifacts
mv package-lock.json package-lock.json.npm-backup
mv node_modules node_modules.npm-backup

# 4. Install with pnpm
pnpm install

# 5. Purge npm backups (after confirming everything works)
rm -rf node_modules.npm-backup package-lock.json.npm-backup
```

## Validation (after migration)

```bash
# Build
time pnpm run build

# Tests
time pnpm vitest run

# TypeScript
pnpm tsc --noEmit

# Lint
pnpm run lint

# E2E (if applicable)
pnpm playwright test --workers=1
```

## Benchmark comparison

```bash
echo "=== disk ==="
echo "npm node_modules:  $(du -sh node_modules.npm-backup 2>/dev/null | cut -f1)"
echo "pnpm node_modules: $(du -sh node_modules | cut -f1)"
echo "=== lockfile ==="
echo "npm:  $(wc -c < package-lock.json.npm-backup 2>/dev/null) bytes"
echo "pnpm: $(wc -c < pnpm-lock.yaml) bytes"
```

## Expected gains (from real-world shop migration)

- node_modules: ~16% smaller (923 MB → 775 MB, -148 MB)
- lockfile: ~35% smaller
- install and build times comparable

## Pitfalls

- Do NOT modify source code during migration — only dependency files
- If tests fail after pnpm install, investigate BEFORE committing — pnpm has stricter module resolution
- After migration, all CI and scripts must reference `pnpm` not `npm`
- Update any Dockerfiles or CI configs that hardcode `npm`
- The task body should include explicit CI-via-background instructions to avoid iteration budget exhaustion during the validation phase
