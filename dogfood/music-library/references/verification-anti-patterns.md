# Anti-Patterns: verification failures

Concrete examples of "Verify, don't assume" violations observed in sessions.
Each entry: what happened, what should have been done instead.

## PR #78 orphan (2026-07-08)

**What happened:** User asked "Why is #78 not merged?" Agent checked PR status (OPEN, approved, CI green, auto-merge null)
and confidently answered "auto-merge wasn't enabled." User replied sarcastically "Jparlais du fait que ça
soit pas sur upstream" — the real question was whether the fix had reached upstream.

**What should have happened:** Before diagnosing merge status, check both repos:
```bash
gh pr list --repo mnlamart/music-library --state merged --search "same title"
# → Found PR #39 upstream — already merged. Fork PR #78 was an orphan.
```

**Rule:** When asked about a PR's merge status, check fork AND upstream before answering. The user may
be asking "why isn't this fix live upstream?" not "why isn't the fork PR merged?"

## PR #76 broken E2E tests (2026-07-08)

**What happened:** PR #76 claimed to "remove broken E2E tests." Agent reviewed the code, saw it removed
3 tests, concluded they were indeed broken, and prepared to merge. User pushed back: "Are you sure the
test were even broken?" Agent ran the tests — all 3 passed.

**What should have happened:**
```bash
git checkout main
npx playwright test tests/e2e/playlists.test.ts --grep "does not show" --reporter=line
```
Never trust a PR's own description of what's "broken." Clone the branch, run the tests, verify independently.

**Rule:** PR titles and bodies are claims, not facts. When a PR says "fix broken X" or "remove broken Y,"
run X or Y yourself before approving. Deletion of working tests is a regression, not a fix.

## Local E2E test setup pitfall

Running Playwright tests locally requires `LITEFS_DIR=/tmp` in `.env`:
```bash
LITEFS_DIR=/tmp npx playwright test tests/e2e/playlists.test.ts --reporter=line
```
Without it, the dev server crashes on `getInstanceInfoSync()` during SSR, returning 500 for all requests.
The test harness doesn't surface this clearly — tests may pass against 500 error pages, producing false
negatives (tests pass but didn't actually test the real page).
