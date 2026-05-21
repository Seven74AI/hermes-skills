# Fix-All-Tests Ticket Template

Template body for a P0 "fix all tests" ticket. Replace placeholders.

```markdown
## Fix ALL test errors and flaky tests on main

Goal: CI must be GREEN on main. Last CI run (URL_OR_DESC) failed.
Fix every failing test, every flaky test, every typecheck error. Zero tolerance.

### Step 1 — Diagnose
```bash
cd /path/to/workspace
git checkout main
npm ci
npx prisma generate && npx prisma generate --sql
npm run test 2>&1 | tee /tmp/vitest.log
npm run test:e2e 2>&1 | tee /tmp/e2e.log
npm run lint
```
Run ALL in background: `terminal("npm run test && npm run test:e2e && npm run lint", background=true, notify_on_complete=true)` + `process(action="wait", timeout=3600)`

### Step 2 — Fix categories (check each)

**A) Known flaky patterns from shop skill:**
- WCAG color-contrast in a11y tests: add `{ disableRules: ['color-contrast'] }` to flaky `expectPageToBeAccessible()` calls
- Prisma transaction race in admin-users tests: wrap `prisma.role.upsert()` in try/catch

**B) Failing unit tests:**
- Read vitest output, identify every `FAIL`
- Fix assertions, mocks, test setup
- Goal: N/N pass

**C) Failing E2E tests:**
- Read playwright output, identify every `FAIL` and `FLAKY`
- Fix selectors, wait strategies, test data
- Goal: N/N pass, 0 flaky

**D) TypeScript errors:**
- Read tsc output, fix every `error TS`
- Goal: clean `tsc --noEmit`

### Step 3 — Verify
```bash
npm run test && npm run test:e2e && npm run lint
# Must pass: ALL green, zero failures
```

### Step 4 — PR
```bash
BRANCH="fix/all-tests-green"
git checkout -b "$BRANCH"
git add -A && git commit -m "fix: all test errors and flaky tests — CI green"
git push origin "$BRANCH"
gh pr create --repo Seven74AI/shop --base main --head "$BRANCH" \
  --title "fix: all test errors and flaky tests — CI green" \
  --label "kanban:$HERMES_KANBAN_TASK"
```

### Rules
- One commit per fix category (squash before PR)
- No skipping tests with `.skip` — fix them
- No `test.only` left behind
- Run full suite before PR — don't rely on CI for first pass
- If a test is fundamentally broken (tests removed feature), delete it with comment explaining why

### Reference
Shop skill: `dogfood/shop` — known flaky patterns, Prisma config, CI workflow.
```

## CLI create command

```bash
hermes kanban --board shop create --assignee coder --max-runtime 3600s --priority 1 \
  "[P0] Fix ALL test errors and flaky tests on main — CI must be green"
```

## Body backfill (shell quoting issues with --body)

```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/shop/kanban.db')
conn.execute('UPDATE tasks SET body=? WHERE id=?', (BODY, 'TICKET_ID'))
conn.commit()
```
