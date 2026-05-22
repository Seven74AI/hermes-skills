# CI Status Check Context Matching

GitHub branch protection required status checks match the **exact** name
of the check run. Emoji-prefixed job names and matrix-suffixed job names will
never match plain-text required contexts, causing auto-merge to hang forever
on "waiting for status to be reported".

## Rule

Required contexts (`["lint", "typecheck", "vitest", "playwright"]`) must match
the **exact** string of the CI job's status check name.

## Pitfall 1 — Emoji `name:` fields

```yaml
# WRONG — check name is "⬣ ESLint", not "lint"
lint:
  name: ⬣ ESLint
  ...

# RIGHT — check name is "lint" (the YAML key)
lint:
  ...
```

Diagnosis:
```bash
# Required contexts
gh api repos/OWNER/REPO/branches/main/protection --jq '.required_status_checks.contexts[]'
# Actual check names
gh pr checks N --repo OWNER/REPO | awk '{print $1}'
```

Fix: remove all job-level `name:` fields from `.github/workflows/*.yml`.
Step-level `- name:` fields are fine — they're cosmetic inside the job.

## Pitfall 2 — Matrix sharding

```yaml
# WRONG — creates "playwright (1)" and "playwright (2)"
# Required context "playwright" matches NEITHER
playwright:
  strategy:
    matrix:
      shard: [1, 2]
```

### Fix A — Remove matrix (simple, slower)

```yaml
playwright:
  runs-on: ubuntu-24.04
  steps:
    - run: npx playwright test  # no --shard
```

Good for small suites. Use when E2E runtime is < 5 min.

### Fix B — Gate job (preserves sharding)

```yaml
playwright:
  strategy:
    fail-fast: false
    matrix:
      shard: [1, 2]
  steps:
    - run: npx playwright test --shard=${{ matrix.shard }}/${{ strategy.job-total }}

playwright-gate:
  needs: playwright
  runs-on: ubuntu-24.04
  if: always()
  steps:
    - name: Check playwright results
      run: |
        if [ "${{ needs.playwright.result }}" = "success" ]; then
          echo "All playwright shards passed"
          exit 0
        else
          echo "Playwright shards failed: ${{ needs.playwright.result }}"
          exit 1
        fi
```

Then update branch protection to use `playwright-gate`:
```bash
gh api --method PUT repos/OWNER/REPO/branches/main/protection --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "typecheck", "vitest", "playwright-gate"]
  },
  ...
}
EOF
```

Also update `deploy` job's `needs:`:
```yaml
deploy:
  needs: [lint, typecheck, vitest, playwright-gate, container]
```

## Real cases

- **shop** (2026-05-21): emoji names `⬣ ESLint` → `lint` mismatch. Fixed in PR #146.
- **music-library** (2026-05-21): emoji names + matrix `playwright (1)/(2)` → `playwright` mismatch. Fixed in PR #2 (emoji) + PR #4 (gate).
- **Standard adopted**: all projects use 2-shard `playwright-gate` pattern. Documented in SKILL.md § Playwright E2E sharding.
