---
name: setup-pre-commit
description: "Set up Husky pre-commit hooks with lint-staged (Prettier or oxfmt), type checking, and tests in the current repo. Use when user wants to add pre-commit hooks, set up Husky, configure lint-staged, or add commit-time formatting/typechecking/testing."
version: 2.0.0
metadata:
  hermes:
    tags: [setup-pre-commit, misc, matt-pocock]
source: mattpocock/skills
---

# Setup Pre-Commit Hooks

## What This Sets Up

- **Husky** pre-commit hook
- **lint-staged** running a formatter (Prettier or oxfmt) on all staged files
- **lint**, **typecheck**, and **test** in the pre-commit hook (mirrors CI minus E2E by default)
- Optionally **Playwright E2E** if user asks for full CI mirror

## Steps

### 1. Detect package manager and formatter

Check for `package-lock.json` (npm), `pnpm-lock.yaml` (pnpm), `yarn.lock` (yarn), `bun.lockb` (bun). Use whichever is present. Default to npm if unclear.

**Formatter choice:** If the project already uses `oxlint` for linting, prefer `oxfmt` (the companion formatter). Otherwise default to Prettier. Ask the user if both are absent.

### 2. Install dependencies

Install as devDependencies:

```
husky lint-staged <formatter>
```

Where `<formatter>` is `prettier` or `oxfmt`.

### 3. Initialize Husky

```bash
npx husky init
```

This creates `.husky/` dir and adds `prepare: "husky"` to package.json.

### 4. Create `.husky/pre-commit`

Write this file (no shebang needed for Husky v9+):

```
npx lint-staged &&
npm run lint &&
npm run typecheck &&
npm run test -- --run
```

**Critical: chain commands with `&&`.** Without `&&`, shell runs every command independently and only the LAST command's exit code matters — a failing `typecheck` (exit 2) is silently ignored if `test` happens to pass or fail differently. This is how type errors slip past pre-commit hooks.

**Adapt**: Replace `npm` with detected package manager. If the repo has no `lint` script, omit that line. If `test` script is vitest, add `-- --run` to prevent watch mode. Always match the CI pipeline order (lint → typecheck → test).

**Playwright E2E (only if user explicitly asks for full CI mirror):** Add `npm run test:e2e:run` as the last line. `test:e2e:run` triggers `pretest:e2e:run` which builds the app first.

### 5. Create `.lintstagedrc`

**Prettier:**
```json
{
  "*.{ts,tsx,js,mjs,cjs,json,md,css}": "prettier --ignore-unknown --write"
}
```

**oxfmt:**
```json
{
  "*.{ts,tsx,js,mjs,cjs,json,md,css}": "oxfmt --write"
}
```

Scope the glob to code file types — `"*"` matches everything (binary, images, etc.) and is sloppy.

oxfmt uses its defaults; no `.oxfmtrc` config file is required unless customizing. The project's `oxlintrc.json` config is separate from oxfmt.

### 6. Create formatter config (if missing)

Only create if no config exists.

**Prettier (`prettierrc`):**
```json
{
  "useTabs": false,
  "tabWidth": 2,
  "printWidth": 80,
  "singleQuote": false,
  "trailingComma": "es5",
  "semi": true,
  "arrowParens": "always"
}
```

**oxfmt:** No config file needed unless customizing. Run `oxfmt --init` to generate one.

### 7. Verify

- [ ] `.husky/pre-commit` exists and is executable
- [ ] `.lintstagedrc` exists
- [ ] `prepare` script in package.json is `"husky"`
- [ ] Formatter config exists (if needed)
- [ ] Run `npx lint-staged` to verify it works on staged files

### 8. Commit

Stage all changed/created files and commit with a descriptive message. **This will run through the new pre-commit hooks — a good smoke test that everything works.** If the vitest suite is large (100+ test files), expect the commit to take 2-3 minutes. Set a generous terminal timeout (600s) on the commit command.

## Notes

- Husky v9+ doesn't need shebangs in hook files
- `prettier --ignore-unknown` skips files Prettier can't parse (images, etc.). `oxfmt --write` handles the same — no `--ignore-unknown` flag needed
- The pre-commit runs lint-staged first (fast, staged-only), then lint, typecheck, and vitest (`--run` to skip watch mode)
- **CI mirror pattern:** pre-commit = CI minus E2E (Playwright is too slow). Order: lint-staged → lint → typecheck → vitest. Only add Playwright if user explicitly asks for full CI mirror
- When oxlint is the linter, the pre-commit hook invokes `npm run lint` which runs `oxlint` — oxlint exits 0 on warnings, only exits non-zero on errors
- oxfmt 0.x uses defaults identical to Prettier defaults; run `oxfmt --init` to generate a config file if customization is needed
- **Switching formatters (prettier → oxfmt):** When replacing prettier with oxfmt, also: (a) `npm uninstall prettier`, (b) remove `"prettier": "..."` config from package.json, (c) update the `format` script from `prettier --write .` to `oxfmt --write .`. Leaving both installed creates a tool conflict.
- **Playwright in pre-commit:** By default skip E2E (too slow — 4-6 min). If the user explicitly asks for it ("run the same test as CI"), add `npm run test:e2e:run` as the last line. Note that `test:e2e:run` already triggers `pretest:e2e:run` which runs `npm run build`.
- **Flaky E2E in pre-commit:** If a pre-existing flaky test blocks the commit, fix it in the same PR (user prefers immediate fixes over deferral). Common flaky patterns: `networkidle` hanging (→ `domcontentloaded`), `waitForResponse` with no timeout (→ assertion with explicit timeout), `toBeVisible` with default 5s timeout (→ 15s). **Never expand timeouts as a first fix — find the root cause.** See `project-ci` skill `references/flaky-e2e-fixes.md` for full diagnosis.
- **Mock data prerequisites:** E2E tests may depend on fixture files (audio blobs, images, configs) that don't exist in the repo because they're .gitignored or need generation. If audio/video player tests fail with `toBeVisible` on transport controls, check that the mock storage has the expected files. See `project-ci` skill `references/e2e-mock-fixtures.md` for the fixture generation pattern.
