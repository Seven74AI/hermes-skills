---
name: music-library
description: "Music Library project configuration — tech stack, repo, tenant."
version: 1.26.0
metadata:
  hermes:
    tags: [music, project, reference]
---

# Music Library — Project Configuration

Load this skill when working on the Music Library app.
Also load `kanban-project-workflow` — it contains the shared PR workflow,
respawn guard, profile sync, and worker tuning patterns.

### Planning flow (grill → PRD → issues)

When the user says **"grill with docs"** (or runs the Matt Pocock flow), **write the decision
record incrementally as each decision locks — do not wait until the end.** On this repo that's
the numbered ADR convention: `docs/decisions/NNN-*.md` (Status starts `Proposed — draft`, flips
to `Accepted` when the grill finishes; include a `Non-goals` section). The `grilling` skill is
only the interview loop (one question at a time, always give a recommended answer, look facts up
in the codebase rather than asking) — it does NOT mention docs, but this user expects a running
ADR updated after each confirmed answer. `to-prd` then gates on a **seam-confirmation** step:
present the proposed test seams (prefer existing seams, fewest new ones) and get the user's OK
before writing the PRD. `to-issues` splits into tracer-bullet vertical slices and quizzes on
granularity/dependencies before publishing.

## GitHub

- **Upstream:** `mnlamart/music-library` — `https://github.com/mnlamart/music-library.git`
- **Fork:** `Seven74AI/music-library` — `https://oauth2:TOKEN@github.com/Seven74AI/music-library.git`

Local working copy: `~/projects/music-library`. Remotes: `origin` = fork, `upstream` = `mnlamart/music-library`.

All feature work lands on the fork first, then consolidation PRs to upstream.

### Creating issues

GitHub issues and PRDs live on `Seven74AI/music-library` (not upstream). Always pass `--repo Seven74AI/music-library` to `gh issue create` — without it, `gh` will default to `mnlamart/music-library` (the repo the clone was originally from).

```bash
gh issue create --repo Seven74AI/music-library --title "..." --body "..." --label "..."
```

## Environment

- `MOCKS=true` — set at runtime in scripts/CI, not in `.env.example`

## Local Dev Setup

The working copy at `~/projects/music-library` persists across sessions.

### `.env` required vars

```bash
DATABASE_URL="file:./data.db?connection_limit=1"
DATABASE_PATH="./prisma/data.db"
CACHE_DATABASE_PATH="./other/cache.db"
LITEFS_DIR="/litefs/data"
SESSION_SECRET="***"
INTERNAL_COMMAND_TOKEN="some-made-up-token"
HONEYPOT_SECRET="super-duper-s3cret"
# Tigris/S3 mock vars
AWS_ACCESS_KEY_ID="mock-access-key"
AWS_SECRET_ACCESS_KEY="mock-secret-key"
AWS_REGION="auto"
AWS_ENDPOINT_URL_S3="https://fly.storage.tigris.dev"
BUCKET_NAME="mock-bucket"
```

### Database setup

On a fresh clone or after a reset, the SQLite database file is empty — no tables exist.
Run migrations before seeding:

```bash
npx prisma migrate deploy   # apply all migrations (non-interactive, works in CI/scripts)
npm run db:seed             # seed test data (5 users, 2 playlists, 4 tracks)
```

**Pitfall:** `prisma migrate dev` is interactive and will fail with `non-interactive` errors
in scripts or terminal sessions. Use `prisma migrate deploy` instead — it applies existing
migrations without prompting.

**Pitfall — `?connection_limit=1` breaks ad-hoc Prisma scripts.** `DATABASE_URL` carries
`?connection_limit=1`, which the `PrismaBetterSqlite3` adapter treats as part of the FILENAME —
an ad-hoc script using the raw URL opens an empty `data.db?connection_limit=1` file and hits
`TableDoesNotExist`. The app strips it via `getDatabaseUrl()` (`app/utils/database-url.server.ts`).
For throwaway repro scripts, pass `DATABASE_URL="file:./data.db"` (no query param) or replicate
`getDatabaseUrl()`. Also: the Prisma CLI and the runtime adapter resolve relative `file:` paths
differently — verify which `.db` actually holds tables with `sqlite3 <file> .tables`.

If the schema has pending drift, run `prisma migrate dev` once interactively to generate
the migration, then `prisma migrate deploy` for subsequent runs.

For a full reset: `npm run db:reset` (wraps `prisma migrate reset --force && prisma generate`).

### Prisma client generation

```bash
npx prisma generate   # required before first typecheck
```

### Running tests

```bash
npx vitest run app/utils/service-playlist.server.test.ts   # single file
npx vitest run                                             # all vitest tests
```

**DB-behavior tests use the real client.** Mocked prisma (`vi.mock("#app/utils/db.server")`)
can't reproduce unique-constraint collisions or upsert matching. For those, import the real
`prisma` (leave `db.server` unmocked) — the harness gives each pool an isolated copy of
`tests/prisma/base.db`. Shared mock fns referenced by `vi.mock` factories need `vi.hoisted()`
when the module under test is statically imported. See `references/integration-testing-real-db.md`.

**Pitfall — pre-commit runs vitest WITHOUT coverage; CI runs WITH `--coverage`.** The
hook (`.husky/pre-commit`) runs `npm run test -- --run` (plain `vitest run`); CI
(`deploy.yml`) runs `npm run test -- --coverage`. A timing-sensitive test passes the hook
locally but times out (5s default) on CI's slower runner under coverage instrumentation —
so "pre-commit passed" does NOT mean "CI vitest will pass". Keep tests lean: don't loop
heavy DB writes to drive in-memory state — exhaust the pure function directly, then assert
the boundary once. (Real case: the play-event 429 test looped `PLAY_EVENT_MAX_PER_WINDOW`=60
full `action()` calls; fixed by calling `consumePlayEventBudget()` in-memory 60×, then one
`action()` for the 429 — and the 429 path short-circuits before any DB access.)

**Pitfall — e2e (Playwright) serves the built bundle, not source.** In `CI=true` mode
Playwright runs `npm run start:mocks` (`NODE_ENV=production tsx .`), which serves
`build/client` — so edits to `app/**` are NOT reflected until you run `npm run build`.
Also `reuseExistingServer: true` reuses whatever is already on the port (e.g. a stale
dev server from a previous session, whose `tsx watch --ignore app/**` won't reload
`app/**` changes). Before verifying e2e changes locally: `npm run build`, then run on a
fresh `PORT` to dodge stale servers. See `references/e2e-testing.md`.

### Browser testing

See `docs/browser-testing-guide.md` for the full manual browser testing guide: dev server setup, test credentials (`kody`/`kodyuser`), page checklist, DevTools tabs, mobile viewport, offline mode, auth flows.

**Interactive browser automation** from Hermes uses `agent-browser` (not the Firecrawl browser tool — the self-hosted Firecrawl stack lacks browser session support). See `references/agent-browser-testing.md` for the setup, core loop, login flow, and pitfalls.

**Pitfall — form submission with agent-browser:** React Router `<Form>` components may not submit via `agent-browser click` alone. Use `agent-browser press Enter` after filling the last field, or click the field first then press Enter. The core loop: `fill @e8 "user" → fill @e9 "pass" → click @e9 → press Enter`.

### Token source & rotation

Canonical token is `GITHUB_TOKEN` in `/root/.hermes/.env` (classic PAT, `repo` + `workflow` scope). Re-wire after rotation:

```bash
T=$(grep -E '^GITHUB_TOKEN=' /root/.hermes/.env | head -1 | sed -E 's/^GITHUB_TOKEN=//' | tr -d '\r\n')
echo "$T" | gh auth login -h github.com --with-token
git remote set-url origin "https://oauth2:$T@github.com/Seven74AI/music-library.git"
git remote set-url upstream "https://oauth2:$T@github.com/mnlamart/music-library.git"
printf 'https://oauth2:%s@github.com\n' "$T" > ~/.git-credentials
```

### Git push

```bash
gh auth token | xargs -I{} git remote set-url origin "https://oauth2:{}@github.com/Seven74AI/music-library.git"
```

## Route Loader Rule — ARCHITECTURAL FIX (supersedes previous bandaid fixes)

**Root cause (verified against React Router v8.2.0 `single-fetch.tsx`):**
`clientLoader.hydrate=true` on a parent layout route (root) triggers React Router's
`foundOptOutRoute` single-fetch path, which excludes layout routes without their own
clientLoaders from hydration data.  The `SingleFetchNoResultError` is silently caught
by `ErrorBoundary` components (e.g. `music.tsx`'s `<OfflineAwareErrorBoundary />`).

### Final state: Unified offline middleware (PR #138, ADR-0015)

The entire offline feature was refactored into a **single middleware layer**.
No route exports `clientLoader` for offline purposes.  `persistOfflineRootShell`
moved into `offlineClientMiddleware`.

Key files:
- `app/middleware/offline-client.middleware.client.ts` — handles online root shell
  persist offline data patching for ALL routes.  Includes a `typeof document === "undefined"`
  server guard (defense-in-depth — React Router v7/v8 keeps `clientMiddleware` and
  `middleware` as separate export slots; `clientMiddleware` does NOT execute during
  SSR, but the guard ensures offline logic stays browser-only regardless).
- `app/features/offline-app/offline-route-policies.client.ts` — unified stub map
  (no more "live" vs "stub" split; sync/async entries)
- `docs/adr/0015-unified-offline-middleware.md` — full decision record

**Dead code removed:** `define-offline-client-loader.ts`, `offline-loader.client.ts`
(`createOfflineClientLoader`, `loadWithOfflineFallback`, `isLikelyNetworkFailure`,
`ServerLoaderData`).

**Exception:** `downloads.tsx` keeps a plain `clientLoader` (no server loader exists;
no `hydrate=true` so no `foundOptOutRoute` trigger).

### Pitfall: wrong comment in `offlineClientMiddleware`

The file `app/middleware/offline-client.middleware.client.ts` contains a comment at
line 57-59 that incorrectly claims:

> React Router v8 runs clientMiddleware during SSR data strategy execution

This is **wrong**. See `references/react-router-middleware-architecture.md` — the Vite
plugin keeps `middleware` and `clientMiddleware` as separate export slots; they are
not cross-mapped. `clientMiddleware` does NOT execute during SSR.

The `typeof document === "undefined"` guard at line 77 is defense-in-depth — it
targets a code path that currently never runs on the server. Do not rely on the comment.

### Pitfall: "No result found for routeId 'root'" on reload in prod

This React Router 8 single-fetch error only occurs on **production builds**
(`react-router build`), not on the Vite dev server. The error only manifests
**when logged in** — the logged-out path does not trigger it.

**Verified root cause (July 2026): React Router 8.2.0 HydrateFallback + `routesParams.size === 0` shortcut.**

`root.tsx` exports `HydrateFallback` (line 161-163). This triggers React Router's
hydration path where `singleFetchLoaderNavigationStrategy` checks
`window.__reactRouterHdrActive` (line 174 of `single-fetch.js`). This flag is
set ONLY by Vite HMR refresh utils (injected during `react-router dev`), NEVER on
initial page load and NEVER in production builds. Source: `refresh-utils.mjs:70-73`
and `rsc-refresh-utils.mjs:28-31` in the `@react-router/dev` package.

Because `__reactRouterHdrActive` is `undefined` on initial load, the guard
`!window.__reactRouterHdrActive` is always `true`. When combined with
`routesParams.size === 0` (all routes already have SSR-embedded data and skip
revalidation), the deferred resolves with `{ routes: {} }` — empty routes.

When `unwrapSingleFetchResult` later looks up `result.routes["root"]`, it's `null`
→ throws `SingleFetchNoResultError`.

The **SSR response is correct** — the embedded stream includes `"root"` data
(confirmed via curl). The manifest is also correct: `hasLoader: true`,
`hasClientLoader: false`, `hasClientMiddleware: true`. The error is in the
client-side revalidation path, not the server.

**Reproduction recipe:**
1. `npm run build && NODE_ENV=production node index.js`
2. Open `http://localhost:3000/login` in a browser, log in as `kody` / `kodylovesyou`
3. After redirect, reload the page → `No result found for routeId "root"` appears
4. The error does NOT reproduce when logged out (different hydration state)

The minified call site is: `errorBoundaries-*.js:2:5707` — `k()` function
looks up `e.routes[routeId]`.

**Verified fix (July 2026): Set `__reactRouterHdrActive` in `offlineClientMiddleware` + inline script defense-in-depth.**

The flag must be set **inside the data strategy execution flow**, right after the
`typeof document === "undefined"` server guard — this is the primary fix.
An inline HTML script provides defense-in-depth by setting the flag at HTML parse
time before React Router modules load.

The middleware runs as part of `runClientMiddleware` → `next()` →
`singleFetchLoaderNavigationStrategy`, so the flag is set right before the
`!window.__reactRouterHdrActive` check. This is the layer that prevents the
empty-routes shortcut.

```typescript
// In offline-client.middleware.client.ts, after the server guard:
if (typeof document === "undefined") {
  return next();
}

// Guard against React Router 8.2.0 single-fetch empty-routes shortcut
window.__reactRouterHdrActive = true;

// ... rest of middleware
```

This mirrors what the Vite HMR refresh utils do in dev (`refresh-utils.mjs`).

**Approaches confirmed NOT to work:**
- Removing `HydrateFallback` export — error still fires (even on cold load)
- Inline `<script>` alone without the middleware — insufficient as the sole fix

See `references/no-result-found-root-routeid.md` for the full trace.

### Pitfall: `navigator.onLine` is `undefined` in Node ≥21

Node.js ≥21 exposes a global `navigator` object, but `navigator.onLine` is `undefined`
(not a boolean).  Any code that reads `navigator.onLine` during SSR and treats it as a
boolean will break on Node ≥21 because `!undefined` is `true`.

**All three affected locations (fix ALL):**

1. `app/features/offline-app/is-offline-environment.ts` — `isOfflineEnvironment()`
2. **`app/hooks/use-online-status.ts` — `readInitialOnlineStatus()` ← SSR-breaking**
3. `app/middleware/offline-client.middleware.client.ts` — defense-in-depth server guard

**Location #2 is the real SSR bug**: `useState(navigator.onLine)` → `undefined` →
falsy → `OfflineStatusBanner` renders "You're offline" during SSR. The banner
breaks client hydration and the page never finishes loading (timed out `page.goto`).

**Correct pattern (all three locations):**
```ts
typeof navigator !== "undefined" &&
  typeof navigator.onLine === "boolean" &&
  !navigator.onLine
```

**⁉ `clientMiddleware` does NOT run during SSR.** React Router v7/v8's Vite plugin
uses two separate middleware export slots:
- `middleware` (server export, in `SERVER_ONLY_ROUTE_EXPORTS`) → executed via
  `runServerMiddlewarePipeline` during SSR `staticHandler.query()`
- `clientMiddleware` (client export, in `CLIENT_NON_COMPONENT_EXPORTS`) → executed via
  `runClientMiddlewarePipeline` during client navigations

They are not cross-mapped.  `root.tsx` only exports `clientMiddleware`, so
`route.module.middleware` is `undefined` during SSR and no client middleware code
executes on the server.  See `references/react-router-middleware-architecture.md`.

**Why PR #140 didn't fix the SSR bug**: it fixed location #1 and added guard #3, but
never checked #2 (`use-online-status.ts`).  The `SingleFetchNoResultError` was not
caused by `offlineClientMiddleware` patching data during SSR — that code path never
executes.  The actual root cause was `readInitialOnlineStatus()` returning
`undefined` during SSR, causing the offline banner to render and breaking hydration.

**Why Playwright didn't catch this:** Playwright runs in a browser where
`navigator.onLine` is always a boolean.  But the bug DID manifest in Playwright —
the SSR HTML contained the offline banner, and `page.goto("/")` timed out because
hydration failed.  No existing E2E test did a login + reload of `/` and checked
for the offline banner in the SSR output.  A targeted SSR hydration test catches it.

See `references/node-navigator-online-ssr-pitfall.md` for the full diagnosis.

### Previous wrong fixes (DO NOT USE)

- **Adding empty `loader()` to all routes** (commit `5a972fb`): bandaid.  `foundOptOutRoute`
  was still true.  Error persisted.
- **Removing `clientLoader` entirely** (PR #136): fixed `SingleFetchNoResultError` but
  broke offline Playwright tests.
- **Restoring `clientLoader` without `hydrate=true`** (PR #137): worked but kept the
  split architecture (clientLoader on root + `defineOfflineClientLoader` on leaf routes).
  Superseded by the unified middleware refactor.

## Tech Stack

- **Runtime:** Node.js 24
- **ORM:** Prisma 7 + SQLite
- **Frontend:** React 19 + Tailwind 4
- **Router:** React Router 8
- **Package manager:** npm (fork), pnpm (upstream)

## Branch Protection & CI

- **Fork:** `Seven74AI/music-library` — `enforce_admins: true`, `required_reviews: 1`, `dismiss_stale_reviews: true`, required checks: `bundle-size, bundle-size-gate, lint, typecheck, vitest, playwright-gate`. Auto-merge ON, delete branch on merge.
- **Workflow:** named `CI`, npm, 2-shard playwright + `playwright-gate` gate job.
- **Deployment:** container + deploy jobs gated behind `github.repository == 'mnlamart/music-library'` — only fire on upstream pushes.

All coder tasks must include `kanban-project-workflow` in skills:

```bash
hermes kanban --board music-library create --assignee coder \
  --skills music-library --skills kanban-project-workflow ...
```

### PR Workflow

**Before making any changes, always pull first:**
```bash
git pull --rebase origin main
```
Local branches go stale fast since multiple agents and kanban workers commit
to the same fork. Skipping this causes merge conflicts and wasted work.

**⛔ Consolidation PR pitfall — branches go stale while open.** If your feature
branch was created more than a few minutes ago, upstream/main may have moved
(previous consolidation PRs merged, dependabot, direct commits).
ALWAYS rebase before creating the consolidation branch:

```bash
# DON'T: git checkout upstream/main -b chore/consolidate-... && git merge old-branch
#       — old-branch may be based on a parent that no longer exists on upstream

# DO: reset to latest upstream first, then re-apply changes
git fetch upstream main && git reset --hard upstream/main
# Re-apply your fixes on the clean base, THEN push
```

Multiple open consolidation PRs that touch the same files are guaranteed to
conflict if they're not all based on the same upstream commit. One clean rebased
PR is always better than several stale ones.

1. Push feature branch to `Seven74AI/music-library` fork
2. Open PR on the fork — review and merge there first
3. Open consolidation PR from fork → upstream using a dedicated branch (NOT fork main directly):
   ```bash
   git fetch origin main
   git fetch upstream main
   git checkout upstream/main -b chore/consolidate-fork-<date>
   git merge origin/main --no-edit

   # Verify no commits were missed
   git log chore/consolidate-fork-<date>..origin/main --oneline
   # MUST be empty.

   git push origin chore/consolidate-fork-<date>
   gh pr create -R mnlamart/music-library --base main \
     --head Seven74AI:chore/consolidate-fork-<date> \
     --title "chore: consolidate fork — <summary>" \
     --body "Consolidation from Seven74AI/music-library fork."
   ```
   Using a dedicated branch instead of `Seven74AI:main` avoids blocking other
   work on the fork while the consolidation PR is open.
4. Consolidation PRs need manual merge by upstream maintainers — auto-merge requires write access to the target repo.
5. After upstream merge, reset the fork to match upstream (see Fork Sync below).

**Human orchestrator shortcut:** when the user explicitly says "create pr directly
on upstream" or "skip the fork PR," go straight to step 3 — branch off
`upstream/main`, merge the feature branch, push to fork, and create the upstream PR.

### Fork Sync

**Pitfall — `git fetch` success is NOT proof of a valid token.** Both repos are
public, so read traffic is unauthenticated — `git fetch`/`pull` succeed even with
an expired/revoked token. Before starting a sync (which needs `gh api` for the
protection removal/restore below), verify the token against the API and read the
current protection state (also public info, no auth needed):

```bash
T=$(git remote get-url origin | sed -E 's|https://oauth2:([^@]+)@.*|\1|')
curl -sS -o /dev/null -w "user=%{http_code}\n" -H "Authorization: token $T" https://api.github.com/user   # 200 = valid, 401 = dead
curl -sS https://api.github.com/repos/Seven74AI/music-library/branches/main | grep '"protected"'
```

Token sources to check when `gh auth status` reports "invalid token":
`~/.config/gh/hosts.yml`, the URL-embedded token in `git remote -v`, and
`~/.git-credentials`. Per-profile homes under `~/.hermes/profiles/<name>/home/`
carry their own copies and may hold a *different* token. If every token returns
401 on `/user`, stop and get a fresh PAT — pushing to protected `main` is
impossible without a working API token.

**Pitfall — force-pushing during CI cancels the run.** The CI workflow has `concurrency: cancel-in-progress: true` (in `deploy.yml`). Every force-push while CI is running cancels the current run. Multiple rapid pushes leave no clean run — all jobs show `cancelled`. **Push once and wait for CI to complete.** See `references/ci-debugging-patterns.md`.

**Pitfall — a fork PR goes `BEHIND` main and auto-merge stalls silently.** When several slices/PRs merge in sequence (the normal kanban parallel flow), a feature branch created before the previous PR merged ends up 1+ commits behind `main`. Under `strict` branch protection (`required_status_checks.strict = true`), GitHub auto-merge will NOT fire on a stale branch — the PR shows `APPROVED` + `MERGEABLE` + all checks green but `mergeStateStatus: BEHIND`, and it sits forever with zero signal. Diagnose the gap and update the branch (merges `main` in, re-runs CI):

```bash
# how far behind / ahead?
gh api repos/Seven74AI/music-library/compare/<branch>...main --jq '{behind_by, ahead_by}'
# fix — note: `gh pr update-branch` is NOT a subcommand in the installed gh; use the REST API
gh api -X PUT repos/Seven74AI/music-library/pulls/<N>/update-branch
```

After updating, checks flip to `pending` and auto-merge completes once green. Watch for this whenever you see `mergeStateStatus` != `CLEAN` on an otherwise-ready PR.

**Pitfall — "N ahead / N behind" after a rebase-merge is usually a FALSE divergence.** When a
consolidation PR is **rebase**-merged upstream (GitHub "rebase and merge", not squash/merge-commit),
upstream re-applies the fork's commits with NEW SHAs. The fork then reports equal counts on both sides
(`git rev-list --left-right --count origin/main...upstream/main` → `"6  6"`), which reads as real
divergence but is the SAME commits under new SHAs. Before force-resetting, confirm:
`git diff origin/main upstream/main --stat` — **empty output = identical trees = safe to
`git reset --hard upstream/main`** (loses nothing). Only a NON-empty diff means genuine fork-only work
that needs a merge or a fresh consolidation PR. (Real case: consolidation PR #166 rebase-merged; the
fork showed 6/6 but `git diff` was empty — the 6 fork commits were superseded by their rebased twins.)

**Pitfall — an embedded token in the remote URL goes stale and breaks `git push`.** If push fails with
`Invalid username or token. Password authentication is not supported for Git operations` while `gh api`
still works, `git remote -v` embeds a stale PAT (`https://git:ghp_...@github.com/...` or
`https://oauth2:...@...`) that overrides the `gh auth git-credential` helper. Strip it so the helper
supplies the current token: `git remote set-url origin https://github.com/Seven74AI/music-library.git`
(same for `upstream`). Prefer plain URLs + the `gh` helper over embedding tokens — an embedded token is
a snapshot that rots on the next rotation (the "Token source & rotation" re-wire below embeds it, so
re-strip the URL after any future rotation).

**Pitfall — restoring branch protection 422s if `restrictions` is missing.** The `PUT` restore body
MUST include `"restrictions": null` (when no push restrictions exist). A `GET` backup omits `restrictions`
entirely in that case, and re-PUTting it fails with `422 "restrictions" wasn't supplied`. The restore JSON
below already includes the field — don't drop it when rewriting.

```bash
# 1. Remove protection
gh api -X DELETE repos/Seven74AI/music-library/branches/main/protection

# 2. Check ahead/behind first — prefer a clean fast-forward when the fork is strictly behind
git rev-list --left-right --count upstream/main...origin/main   # prints "<upstream-only> <fork-only>"

# 2a. Fork has 0 unique commits (right == 0): fast-forward, NO history rewrite, NO force-push
git checkout main
git merge --ff-only upstream/main
git push origin main

# 2b. Fork diverged (right > 0): must rewrite
git checkout main
git reset --hard upstream/main
git push --force origin main

# 3. Restore protection
cat > /tmp/branch-protection.json << 'JSONEOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["bundle-size", "bundle-size-gate", "lint", "playwright-gate", "typecheck", "vitest"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSONEOF
gh api -X PUT repos/Seven74AI/music-library/branches/main/protection \
  --input /tmp/branch-protection.json

# 4. Re-enable auto-merge
gh api -X PATCH repos/Seven74AI/music-library \
  -f allow_auto_merge=true -f delete_branch_on_merge=true

# 5. Clean up consolidation branch
git branch -D chore/consolidate-fork-<date>
git push origin --delete chore/consolidate-fork-<date>
```

## Code Review

Reviewer kanban tasks are only for **fork PRs** (`Seven74AI/music-library`).
Upstream PRs (`mnlamart/music-library`) are reviewed by upstream maintainers — just open and wait.

**Exception:** when the user explicitly asks you to review an upstream PR (e.g. "code review
https://github.com/mnlamart/music-library/pull/140"), do it — but use the correct `--repo` flag.

**How to review:** review directly — read the diff, check files, produce findings inline.
Do NOT delegate reviews to sub-agents. Sub-agents die silently (OOM, push rejection on
stale bases), leaving the user with nothing after 40+ minute waits. Direct execution is
always faster for this repo's PR sizes.

**For already-merged PRs:** the review must also check whether the fix actually resolved
the reported problem. Read the PR body for the original issue description, then verify:
- Is the fix deployed? (check deploy workflow, Fly.io status)
- Does the bug still manifest in production? (curl, browser)
- Did the fix address the root cause or just symptoms? (trace ALL code paths, not just the
  one the PR author identified)

If the bug persists post-deploy, flag it explicitly: "⚠️ Merged and deployed, but the bug
still manifests — the fix didn't address the root cause."

### Pitfall — repo mismatch

Fork and upstream have **independent PR numbering**. `#140` on `Seven74AI/music-library`
is a completely different PR from `#140` on `mnlamart/music-library`. When the user
provides a URL, extract the `org/repo` from it and pass it to `gh pr view --repo`.
Do NOT default to `--repo Seven74AI/music-library` just because most work happens there.

```bash
# Wrong: defaults to fork — may pull a completely different PR
gh pr view 140 --repo Seven74AI/music-library  # ❌

# Right: extract from the URL the user gave you
gh pr view 140 --repo mnlamart/music-library   # ✓
```

Always log the full `--repo org/repo` in your `gh pr view` call so you can verify it
matches the URL the user provided.

### Pitfall — fix doesn't work in production (STOP AND INVESTIGATE, don't fix more)

When the user reports that a deployed fix didn't solve the problem ("still broken in prod"),
**do NOT create another fix PR**. STOP adding patches — the root cause is still unknown.
Additional fixes pollute the codebase with dead guards.

**What to do instead:**
1. Verify the fix was actually deployed (check Fly.io deploy logs, CI runs on main)
2. Access the production URL to see the actual error (curl, browser)
3. Trace the full rendering path from root layout → route → component
4. Check if the original diagnosis was wrong (e.g., assumed `clientMiddleware` runs during SSR)
5. Ask the user what they actually see (blank page? error? offline banner? server error?)

The `navigator.onLine` fix in `use-online-status.ts` fixed the `OfflineStatusBanner` SSR issue,
but if the problem isn't the offline banner, that fix is irrelevant.

### Pitfall — documentation-as-fix

When a PR responds to a bug report, audit finding, or actionable issue but the change
is documentation-only (comments, README edits), flag it.  A PR that describes a problem
without fixing it "passes spec" but doesn't close the loop.  Call it out explicitly:
"⚠️ This documents the problem but doesn't fix it — the underlying issue still exists."

Create a reviewer kanban task for fork PRs (not a GitHub issue):

```bash
hermes kanban --board music-library create \
  "Review: PR #N — <short summary>" \
  --assignee reviewer \
  --skill music-library --skill kanban-project-workflow --skill code-review \
  --priority 3 \
  --body '## Context
PR #N at <repo>. Changes: <bullet list>.
## Review axes: Correctness, Completeness, Standards, Test coverage
## CI status: <checks>'
```

Then `notify-subscribe` on the task.

## Domain Architecture

**Scale fact:** a standard user library is ~15k tracks (cuid IDs, ~25 chars each). Any design that serializes or iterates the *full* track list — queue persistence, shuffle state, play-order snapshots — must NOT write O(library-size) blobs (a 15k-ID JSON list is ~420KB, rewritten on every queue mutation). Prefer re-derivation (store context + position) and seeded PRNGs (store a 32-bit `shuffleSeed`, not the permutation) over materializing the track-ID list.

Audio archiving was reimplemented (reversing ADR-004). Settled decisions in `docs/CONTEXT.md`. Key decisions:

- **#5 (Error categorization)**: yt-dlp stderr → 7 categories, retry logic
- **#18 (Idempotent enqueue)**: Unique constraint caught, silently skips
- **#22 (Audio serving)**: No redirect — return presigned URL directly, client fetches it
- **#23 (Null durations)**: Display convention (`--:--`), not a playback issue
- **ADR-0015 (Unified offline middleware)**: Single middleware layer handles all offline
  data; no route exports clientLoader for offline. Supersedes PRs #136/#137.
- **ADR-017 (Cross-device queue persistence + play history) — ✅ SHIPPED (Aug 2026, PRs #245–249)**:
  `PlayerState` table (one row/user: `playContext`, `currentTrackId`, `upNextIds`,
  `shuffleSeed`, `loopMode`) + nullable `playId` column on `UsageEvent` + `[userId, type,
  createdAt]` index. Seeded shuffle (`createSeededRandom`/mulberry32 in `queue-shuffle.ts`;
  `LoopMode` union now derived from a `LOOP_MODES` const array in `queue-navigation.ts` — single
  source of truth). New `/history` route (cursor pagination + infinite scroll, per-play rows,
  completed badge via `playId`, skip dangling track IDs). Restore-and-wait (no autoplay); spine
  re-derived from context, never snapshotted; debounced ~1s write + unload flush; offline partial
  restore (current + upNext if downloaded, spine backfilled on reconnect); logout keeps the queue.
  Full record: `docs/decisions/017-cross-device-queue-persistence-play-history.md` and
  `docs/specs/queue-persistence-play-history-prd.md`. Review note #2 (reconnect backfill can discard
  in-session offline mutations — a freshest-wins merge) is a documented non-goal/follow-up.

- **Public playlist sync (by URL) — ⚠️ UNMERGED**: `syncServicePlaylistByUrl()` syncs
  public/unlisted YouTube playlists the user does **not** own, using the API key (no OAuth
  connection). This feature + its `syncSource` column live on the **UNMERGED**
  `feat/sync-playlist-by-url` branch, NOT upstream/main. Current `prisma/schema.prisma` keeps
  `ServicePlaylist` keyed globally on `[serviceId, externalId]` (no `syncSource`). Verify the
  actual schema before trusting these docs. See `references/public-playlist-sync.md`
  (aspirational) and `references/cross-user-unique-key-bugs.md` (bug class + fix + test pattern).

### Pitfall: YouTube OAuth `Connection` unique key is global (multi-user corruption)

`Connection` has `@@unique([providerName, providerId])` (no `userId`), but the YouTube OAuth
callback (`app/routes/music+/services+/youtube+/callback.tsx`) hardcodes `providerId: "youtube"`
and its `update` branch never sets `userId`. Every YouTube connection collides on
`("youtube","youtube")` — only ONE can exist globally. The second user who connects appears
"not connected" (lookup is `findFirst({ providerName, userId })` in
`service-connection.server.ts` → `resolveYouTubeAccessToken`), and the first user's tokens get
silently overwritten. Login providers (`auth.$provider.callback.ts`) use
`providerId: String(profile.id)` correctly; YouTube must use the real channel id (from
`getYouTubeUserInfo()` → `channel.id`). See `references/youtube-oauth-connection-bug.md`.

Condensed implementation reference: `references/audio-archiving-implementation.md`.

## Kanban Tasks

```bash
# Coder
hermes kanban --board music-library create \
  "Task title" \
  --assignee coder \
  --skill music-library --skill kanban-project-workflow --skill implement --skill tdd --skill code-review \
  --body "Task description." \
  --parent <parent_task_id>

# Reviewer
hermes kanban --board music-library create \
  "Review: PR #N" \
  --assignee reviewer \
  --skill music-library --skill kanban-project-workflow --skill code-review
```

Title is the positional argument; body uses `--body`.

**Do NOT use `--initial-status blocked` for ordinary coder cards.** That flag is for cards
requiring immediate human ops (the R3 gate). Normal coder tasks default to `ready`, and the
dispatcher picks them up; sequence them with `--parent` (repeatable) instead — a child stays
`todo` until its parent completes. To capture a newly created task id, pass `--json` and
`grep '"id"'` — do NOT pipe to `python3 -c` to parse the JSON (that trips the pipe-to-interpreter
security approval and blocks the command).

**Pitfall — malformed `review-required` block causes a duplicate-worker respawn loop.** A coder's
"block for review" must be a plain `kanban_block(reason="review-required: ...")` with **no `kind`**.
If the coder passes `kind="dependency"` (or any kind) without a real parent link, the dispatcher
treats the block as unsatisfiable and re-promotes the task, spawning a **duplicate worker** on the
same task. Symptoms: the task flips back to `running` right after the coder blocked for review; two
live worker PIDs appear for one task (`ps aux | grep 'work kanban task <id>'`); events show
`protocol_violation` / `gave_up` ("worker exited cleanly rc=0 without calling kanban_complete or
kanban_block"). The work itself is fine (PR open, CI green) — it's the block call, not the code. Fix:
kill the duplicate PIDs and let the single task re-block cleanly, or unblock/re-claim once the PR merges.
(This is board-agnostic; belongs in `kanban-project-workflow` long-term.)

Subscriptions are per-task, not inherited by child tasks — subscribe each task, including
children, individually:
```bash
hermes kanban --board music-library notify-subscribe <task_id> --platform telegram --chat-id 1811944606
```

**Monitoring a running worker — `show` ≠ `log`.** When the user asks "how is it going" / "is it stuck", don't infer progress from `hermes kanban show <task>` — its heartbeat events only prove the worker is *alive*. A task legitimately runs 30+ min on a big vertical slice. Read `hermes kanban --board music-library log <task>` and look for real terminal activity (`patch`/`review diff`, `npm run typecheck`/`lint`/`vitest` runs, `git commit`) to confirm actual progress vs. idle spinning. Watch for `exit 124` on `git commit` — that's the pre-commit hook timing out (lint-staged→oxlint→typecheck→vitest→playwright), the one recurring friction point; the worker retries with `--no-verify`.

## References

Happy-path only — no pitfalls, gotchas, symptoms, or anti-patterns. When adding new reference files,
state what to do, not what to avoid.

- `references/search.md` — FTS5 architecture, cursor pagination, caching, icons, bottom nav z-index hierarchy, artist/album page routes
- `references/fts5-admin.md` — FTS5 index rebuild commands, health check queries, admin page route
- `references/fts5-rebuild.md` — FTS5 rebuild commands, admin page, diagnosis
- `references/github-operations.md` — `--repo` flag, cross-repo PRs, label management
- `references/audio-archiving-implementation.md` — models, yt-dlp command, worker loop, retry strategy
- `references/public-playlist-sync.md` — sync-by-URL feature: `syncSource` schema, API-key vs OAuth auth paths, `SyncAuth` threading, provider seams, `this`-binding pitfall
- `references/cross-user-unique-key-bugs.md` — cross-user unique-key clobbering bug class (Connection + ServicePlaylist): diagnosis workflow, fix + integration-test pattern, intentionally-global models, docs-drift trap
- `references/youtube-oauth-connection-bug.md` — YouTube OAuth `Connection` global-unique-key bug, repro recipe, better-sqlite3 `?connection_limit=1` gotcha
- `references/integration-testing-real-db.md` — writing tests against the real SQLite test DB (per-pool harness, real `prisma`, `createUser` fixture, `vi.hoisted` mock fns)
- `references/cross-playlist-bulk-operations.md` — API routes for bulk library/playlist operations
- `references/db-performance-audit.md` — Prisma batch explosion, over-fetching patterns, profiling workflow
- `references/dependency-migrations.md` — step-by-step recipes for major version bumps
- `references/radix-sheet-playwright-testing.md` — Radix Sheet `aria-hidden` interferes with Playwright `getByRole` (accessibility tree exclusion); CSS locators work but can cause hangs; prefer verifying sheet unmount over checking external elements
- `references/e2e-audio-fixtures.md` — dummy MP3 prerequisites for transport E2E tests
- `references/e2e-responsive-locators.md` — locators that break on desktop viewport (md:hidden elements) + strict mode violations (regex matching URL paths in error pages)
- `references/agent-browser-testing.md` — local interactive browser testing with `agent-browser` CLI
- `references/browser-testing-setup.md` — manual browser testing: dev setup, credentials, agent-browser workflow, login flow
- `references/e2e-testing.md` — commands, env config, webServer setup, nested Radix Escape counts, CSS z-index overlay rules, toast dismissal (Radix toast has no `role="status"` → use `data-testid="toast"`; stale-`build/` pitfall)
- `references/player-now-playing-sheet.md` — mobile now-playing view architecture
- `references/serwist-navigation-route-method.md` — service worker navigation method internals
- `references/storage-test-fixtures.md` — local file fixture pattern for audio/image test routes
- `references/react-router-typescript-patterns.md` — BreadcrumbHandle Zod inference fix, JSX && narrowing for Prisma relations
- `references/react-router-8-client-action.md` — clientAction proxy pattern for React Router 8 code-split routes
- `references/ci-debugging-patterns.md` — verify pre-existing CI failures, gh CLI for run/job inspection, concurrency cancels runs on force push
- `references/mobile-layout.md` — z-index hierarchy, --bottom-bar-height CSS var, sheet positioning, search overlay
- `references/autoplay-guide.md` — browser autoplay blocking, getAutoplayPolicy API, guide dialog pattern
- `references/autoplay-next-track.md` — next-track auto-advance on lock screen: symptom→cause distinction (permission vs background-suppression), prefetch-next-URL + keep-mediaSession-playing fix
- `references/autoplay-user-gesture-lock.md` — Chromium per-element user-gesture lock; unlock-on-first-gesture (always-mount `<audio>` + one-shot `load()`); one-shot-flag pitfall; scope: fixes first-play-from-tap, NOT locked-screen next-track
- `references/react-router-single-fetch-layout-loaders.md` — `clientLoader.hydrate=true` on parent layouts is an anti-pattern; verified React Router v8.2.0 single-fetch internals; correct fix is removing clientLoader from root, not adding loaders to children
- `references/react-router-middleware-architecture.md` — React Router v7/v8 has two separate middleware export slots (`middleware` for server, `clientMiddleware` for client); they are not cross-mapped; `clientMiddleware` does NOT execute during SSR; full trace from `handleDocumentRequest` through `runServerMiddlewarePipeline`
- `references/node-navigator-online-ssr-pitfall.md` — Node 21+ navigator.onLine SSR pitfall: symptoms, fix, detection, Playwright gap, and corrected SSR execution analysis
- `references/no-result-found-root-routeid.md` — `HydrateFallback` + `routesParams.size === 0` shortcut causes `No result found for routeId "root"`; `__reactRouterHdrActive` only set by Vite HMR, never on initial load
- `references/react-router-source-tracing.md` — workflow for tracing React Router internals from source (clone repo, cross-reference dist vs source, check Vite-injected runtime files)
- `references/usage-analytics.md` — play-counter architecture: `UsageEvent` vs `DailyUsageStat` vs `DailyActiveUser`, play_started/play_completed semantics (≥50% heuristic), per-user rate limit, `trackId` tracked-but-not-surfaced + missing index
- `references/player-state-queue-architecture.md` — in-memory player state, spine/order/position/upNext model, deterministic spine orders, unseeded index-based shuffle, hydration batches — foundation for cross-device queue persistence
- `templates/oxlintrc.json` — oxlint configuration template
