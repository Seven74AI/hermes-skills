---
name: dependency-upgrades
description: Patterns for upgrading npm dependencies with breaking changes — safe bumps, major migrations, type fixes, and CI verification.
version: 1.0.0
metadata:
  hermes:
    tags: [npm, upgrades, dependencies, migrations, breaking-changes]
---

# Dependency Upgrades

Systematic approach for batch-upgrading npm packages, especially major versions with breaking changes.

## Triggers

- User asks "what can we update", "check for updates", "upgrade everything"
- `npm outdated` shows available updates
- After a major framework upgrade, user wants to catch up lagging deps

## Workflow

### 1. Audit: `npm outdated`

Categorize into:
- **Safe** (patch/minor within `^`): `npm update` — no code changes needed
- **Major** (new semver major): `npm install pkg@latest` — expect breaking changes

### 2. Install everything at once

For batch major upgrades, install all in one `npm install` command. This avoids repeated `node_modules` churn and lets you fix all type errors in a single pass.

```bash
npm install pkg-a@latest pkg-b@latest pkg-c@latest ...
```

### 3. Fix type errors

Run `npm run typecheck` and fix systematically. Common categories:

- **Import path changes** (ESM-only, new entrypoints)
- **API renames** (method/property name changes)
- **Type narrowing** (return types now nullable, need `!` or guards)
- **Removed APIs** (need replacement API)

### 4. Verify

```bash
npm run typecheck && npm run test -- --run && npm run lint
```

Also verify the production build/server starts — especially for Express/backend upgrades where tsx dev mode can mask crashes in the bundled production build.

### 5. Commit and PR

- Commit with a message listing every package and its version change
- Push to a branch, open PR
- Wait for CI (especially Playwright E2E if backend changes)

## ⛔ Pitfalls

**tsx dev mode masks production-only crashes.** When upgrading Express or any server framework, the tsx dev path may load TypeScript source directly and skip evaluation of certain code paths. The esbuild-bundled production server (`server-build/index.js`) may crash on the same code because it resolves imports differently. Always test BOTH paths:

```bash
# Dev (tsx) — may work fine
NODE_ENV=production PORT=3099 npx tsx .

# Production (bundled) — the real test
npm run build && PORT=3099 node ./server-build/index.js
```

Observed: Express v5 wildcard routes worked fine with tsx but crashed the bundled server with `PathError: Missing parameter name at index 1: *`.

## Common migrations

See reference files for library-specific migration guides:

- `references/express-v5.md` — Express v5 wildcard routes, path-to-regexp v8
- `references/zod-v4.md` — Zod v4 breaking changes
- `references/set-cookie-parser-v3.md` — ESM-only, parseString nullable
- `references/types-node-v26.md` — rmdirSync removal
