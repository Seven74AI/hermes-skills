# CI Playwright Log Batch Analysis

Technique for downloading and parsing Playwright CI logs across multiple PRs to
identify patterns, group failures by test file, and find systemic vs PR-specific issues.

## Download raw logs

```bash
# Get job IDs for failed playwright jobs on a run
gh run view <run_id> --repo <org>/<repo> --json jobs \
  --jq '.jobs[] | select(.name | startswith("playwright") and .conclusion=="failure") | .databaseId'

# Download full raw log (up to ~2MB, avoids the 50KB --log truncation)
curl -sL "https://api.github.com/repos/<org>/<repo>/actions/jobs/<job_id>/logs" \
  -H "Authorization: Bearer $(gh auth token)" -o <output_file>.log

# Check size — logs under 500 bytes are "not found" (expired)
wc -c <output_file>.log
```

## Parse failures by test file

Playwright reports test failures in two patterns:

1. **Direct:** `N) [browser] › path/to/file.spec.ts:line:col › test name`
2. **Error context:** `Error Context: test-results/<encoded-test-name>-chromium/error-context.md`

```bash
# Extract unique failing test files
grep -oP 'tests/e2e/[^:]+\.(spec|test)\.ts' <log>.log | sort | uniq -c | sort -rn

# Extract error types
grep "Error: " <log>.log | sed 's/.*Error: //' | sort | uniq -c | sort -rn | head -15
```

## Cross-reference across PRs

```bash
# For each PR, collect failing test files
for pr in 268 269 270 271; do
  echo "=== PR #$pr ==="
  curl -sL "https://api.github.com/repos/X/Y/actions/jobs/<job_id>/logs" \
    -H "Authorization: Bearer $(gh auth token)" \
    | grep -oP 'tests/e2e/[^:]+\.test\.ts' | sort | uniq -c
done
```

## Common error pattern → root cause mapping

| Error | Likely cause |
|---|---|
| `expect(locator).toBeVisible() failed` (30s) | Page not rendering, JS error, CSP block |
| `TimeoutError: page.waitForURL` | Redirect not happening, routing broken |
| `locator.click: Test timeout of 30000ms exceeded` | Interaction hung, element never appears |
| `Cannot read properties of undefined (reading 'id')` | JS runtime error in app code |
| `browserType.launch: Executable doesn't exist` | Playwright browsers not installed in CI |

## Identify systemic vs PR-specific

Systemic failures appear on `main` too:
```bash
gh run list --repo <org>/<repo> --branch main --workflow <workflow> --limit 3 --json conclusion
```

If `main` has the same `failure` conclusion → systemic, not introduced by the PR.
This is the key check before spending time debugging a single PR's test failures.

## Real case (shop 2026-05-31)

4 PRs all had playwright failures. Pattern:
- `a11y.test.ts`, `2fa.test.ts`, `passkey.test.ts`, `onboarding.test.ts` — all `toBeVisible() timeout`
- Root cause: CSP `script-src-elem` blocking inline scripts needed for React Router 7 lazy route hydration
- Admin pages returned raw JSON `{"stats":{...}}` instead of HTML — lazy components never loaded
- `main` branch had same failures → systemic, not introduced by any PR
