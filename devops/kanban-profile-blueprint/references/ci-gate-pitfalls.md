# CI Gate Pitfalls — `|| true` and `--if-present`

Systemic CI issues that silently swallow errors. Found on shop (3×) and music-library.

## Pattern 1: `|| true` on typecheck/lint/test

```yaml
# BROKEN — CI always green
run: pnpm typecheck || true
```

The `|| true` ensures the step exits 0 regardless of tsc errors.
Common on Epic Stack projects where the scaffold CI had it.

**Check both upstream AND fork** — the fork can drift and re-introduce
the bug even after upstream is fixed.

```bash
# Audit
curl -s https://raw.githubusercontent.com/ORG/REPO/main/.github/workflows/deploy.yml | grep '|| true'
curl -s https://raw.githubusercontent.com/Seven74AI/REPO/main/.github/workflows/deploy.yml | grep '|| true'
```

Real cases:
- shop: removed in `15f1d1e`, re-introduced by consolidation `0774571`, 
  re-introduced again on fork (May 21)
- music-library: found on upstream `mnlamart/music-library` — `pnpm typecheck || true`

## Pattern 2: `--if-present` on npm scripts

```yaml
# BROKEN — silently skips if script missing
run: npm run typecheck --if-present
```

`--if-present` exits 0 if the script doesn't exist in package.json.
If someone renames `typecheck` → `type-check`, CI stays green forever.

```bash
# Audit
grep -rn '\-\-if-present' .github/workflows/
```

Real case: music-library fork CI had `npm run typecheck --if-present`

## Fix

```yaml
# CORRECT — fails loudly
run: pnpm typecheck
run: npm run typecheck
```

## Prevention

After any PR that touches CI workflow, verify:
```bash
grep '|| true' .github/workflows/deploy.yml    # must return NOTHING
grep '\-\-if-present' .github/workflows/deploy.yml  # must return NOTHING
```
