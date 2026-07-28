---
name: music-library
description: "Music Library project configuration — tech stack, repo, tenant."
version: 1.23.0
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

### Prisma client generation

```bash
npx prisma generate   # required before first typecheck
```

### Running tests

```bash
npx vitest run app/utils/service-playlist.server.test.ts   # single file
npx vitest run                                             # all vitest tests
```

### Git push

```bash
gh auth token | xargs -I{} git remote set-url origin "https://oauth2:{}@github.com/Seven74AI/music-library.git"
```

## Route Loader Rule (PITFALL)

`root.tsx` uses `clientLoader.hydrate = true` via `defineOfflineClientLoader("root")`.
This means **every route in the matched tree MUST export a loader** — layout routes
AND leaf routes. Routes without a loader are excluded from the single-fetch
hydration response, causing:

```
SingleFetchNoResultError: No result found for routeId "..."
```

A route that exports an `ErrorBoundary` silently swallows the error, hiding the
problem.

**When fixing `SingleFetchNoResultError`, always run the scan script to find ALL
missing loaders — don't stop at the one the user reported.** See
`references/react-router-single-fetch-layout-loaders.md` for the verification
script and the full list of affected routes.

Add to any route lacking a loader:

```tsx
import { data } from "react-router";

export function loader() {
  return data({});
}
```

After adding loaders, always run `npx react-router typegen && npx tsc --noEmit`.

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

**How to review:** review directly — read the diff, check files, produce findings inline.
Do NOT delegate reviews to sub-agents. Sub-agents die silently (OOM, push rejection on
stale bases), leaving the user with nothing after 40+ minute waits. Direct execution is
always faster for this repo's PR sizes.

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
- `references/e2e-audio-fixtures.md` — dummy MP3 prerequisites for transport E2E tests
- `references/e2e-testing.md` — commands, env config, webServer setup
- `references/player-now-playing-sheet.md` — mobile now-playing view architecture
- `references/serwist-navigation-route-method.md` — service worker navigation method internals
- `references/storage-test-fixtures.md` — local file fixture pattern for audio/image test routes
- `references/react-router-typescript-patterns.md` — BreadcrumbHandle Zod inference fix, JSX && narrowing for Prisma relations
- `references/react-router-8-client-action.md` — clientAction proxy pattern for React Router 8 code-split routes
- `references/ci-debugging-patterns.md` — verify pre-existing CI failures, gh CLI for run/job inspection
- `references/mobile-layout.md` — z-index hierarchy, --bottom-bar-height CSS var, sheet positioning, search overlay
- `references/autoplay-guide.md` — browser autoplay blocking, getAutoplayPolicy API, guide dialog pattern
- `references/react-router-single-fetch-layout-loaders.md` — layout routes must export a loader when `clientLoader.hydrate` is on a parent; SingleFetchNoResultError pattern
- `templates/oxlintrc.json` — oxlint configuration template
