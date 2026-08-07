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

### Browser testing

See `docs/browser-testing-guide.md` for the full manual browser testing guide: dev server setup, test credentials (`kody`/`kodyuser`), page checklist, DevTools tabs, mobile viewport, offline mode, auth flows.

**Interactive browser automation** from Hermes uses `agent-browser` (not the Firecrawl browser tool — the self-hosted Firecrawl stack lacks browser session support). See `references/agent-browser-testing.md` for the setup, core loop, login flow, and pitfalls.

**Pitfall — form submission with agent-browser:** React Router `<Form>` components may not submit via `agent-browser click` alone. Use `agent-browser press Enter` after filling the last field, or click the field first then press Enter. The core loop: `fill @e8 "user" → fill @e9 "pass" → click @e9 → press Enter`.

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

**Pitfall — force-pushing during CI cancels the run.** The CI workflow has `concurrency: cancel-in-progress: true` (in `deploy.yml`). Every force-push while CI is running cancels the current run. Multiple rapid pushes leave no clean run — all jobs show `cancelled`. **Push once and wait for CI to complete.** See `references/ci-debugging-patterns.md`.

```bash
# 1. Remove protection
gh api -X DELETE repos/Seven74AI/music-library/branches/main/protection

# 2. Force push
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

Audio archiving was reimplemented (reversing ADR-004). Settled decisions in `docs/CONTEXT.md`. Key decisions:

- **#5 (Error categorization)**: yt-dlp stderr → 7 categories, retry logic
- **#18 (Idempotent enqueue)**: Unique constraint caught, silently skips
- **#22 (Audio serving)**: No redirect — return presigned URL directly, client fetches it
- **#23 (Null durations)**: Display convention (`--:--`), not a playback issue
- **ADR-0015 (Unified offline middleware)**: Single middleware layer handles all offline
  data; no route exports clientLoader for offline. Supersedes PRs #136/#137.

Condensed implementation reference: `references/audio-archiving-implementation.md`.

## Kanban Tasks

```bash
# Coder
hermes kanban --board music-library create \
  "Task title" \
  --assignee coder \
  --skill music-library --skill kanban-project-workflow --skill implement --skill tdd --skill code-review \
  --body "Task description." \
  --parent <parent_task_id> \
  --initial-status blocked

# Reviewer
hermes kanban --board music-library create \
  "Review: PR #N" \
  --assignee reviewer \
  --skill music-library --skill kanban-project-workflow --skill code-review
```

Title is the positional argument; body uses `--body`.

Subscriptions are per-task, not inherited by child tasks:
```bash
hermes kanban --board music-library notify-subscribe <task_id> --platform telegram --chat-id 1811944606
```

## References

Happy-path only — no pitfalls, gotchas, symptoms, or anti-patterns. When adding new reference files,
state what to do, not what to avoid.

- `references/search.md` — FTS5 architecture, cursor pagination, caching, icons, bottom nav z-index hierarchy, artist/album page routes
- `references/fts5-admin.md` — FTS5 index rebuild commands, health check queries, admin page route
- `references/fts5-rebuild.md` — FTS5 rebuild commands, admin page, diagnosis
- `references/github-operations.md` — `--repo` flag, cross-repo PRs, label management
- `references/audio-archiving-implementation.md` — models, yt-dlp command, worker loop, retry strategy
- `references/cross-playlist-bulk-operations.md` — API routes for bulk library/playlist operations
- `references/db-performance-audit.md` — Prisma batch explosion, over-fetching patterns, profiling workflow
- `references/dependency-migrations.md` — step-by-step recipes for major version bumps
- `references/radix-sheet-playwright-testing.md` — Radix Sheet `aria-hidden` interferes with Playwright `getByRole` (accessibility tree exclusion); CSS locators work but can cause hangs; prefer verifying sheet unmount over checking external elements
- `references/e2e-audio-fixtures.md` — dummy MP3 prerequisites for transport E2E tests
- `references/e2e-responsive-locators.md` — locators that break on desktop viewport (md:hidden elements) + strict mode violations (regex matching URL paths in error pages)
- `references/agent-browser-testing.md` — local interactive browser testing with `agent-browser` CLI
- `references/browser-testing-setup.md` — manual browser testing: dev setup, credentials, agent-browser workflow, login flow
- `references/e2e-testing.md` — commands, env config, webServer setup, nested Radix Escape counts, CSS z-index overlay click bypass with page.evaluate
- `references/player-now-playing-sheet.md` — mobile now-playing view architecture
- `references/serwist-navigation-route-method.md` — service worker navigation method internals
- `references/storage-test-fixtures.md` — local file fixture pattern for audio/image test routes
- `references/react-router-typescript-patterns.md` — BreadcrumbHandle Zod inference fix, JSX && narrowing for Prisma relations
- `references/react-router-8-client-action.md` — clientAction proxy pattern for React Router 8 code-split routes
- `references/ci-debugging-patterns.md` — verify pre-existing CI failures, gh CLI for run/job inspection, concurrency cancels runs on force push
- `references/mobile-layout.md` — z-index hierarchy, --bottom-bar-height CSS var, sheet positioning, search overlay
- `references/autoplay-guide.md` — browser autoplay blocking, getAutoplayPolicy API, guide dialog pattern
- `references/react-router-single-fetch-layout-loaders.md` — `clientLoader.hydrate=true` on parent layouts is an anti-pattern; verified React Router v8.2.0 single-fetch internals; correct fix is removing clientLoader from root, not adding loaders to children
- `references/react-router-middleware-architecture.md` — React Router v7/v8 has two separate middleware export slots (`middleware` for server, `clientMiddleware` for client); they are not cross-mapped; `clientMiddleware` does NOT execute during SSR; full trace from `handleDocumentRequest` through `runServerMiddlewarePipeline`
- `references/node-navigator-online-ssr-pitfall.md` — Node 21+ navigator.onLine SSR pitfall: symptoms, fix, detection, Playwright gap, and corrected SSR execution analysis
- `references/no-result-found-root-routeid.md` — `HydrateFallback` + `routesParams.size === 0` shortcut causes `No result found for routeId "root"`; `__reactRouterHdrActive` only set by Vite HMR, never on initial load
- `references/react-router-source-tracing.md` — workflow for tracing React Router internals from source (clone repo, cross-reference dist vs source, check Vite-injected runtime files)
- `templates/oxlintrc.json` — oxlint configuration template
