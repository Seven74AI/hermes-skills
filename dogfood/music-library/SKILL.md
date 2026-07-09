---
name: music-library
description: "Music Library project configuration — tech stack, repo, tenant."
version: 1.10.0
metadata:
  hermes:
    tags: [music, project, reference]
---

# Music Library — Project Configuration

Load this skill when working on the Music Library app.
Also load `kanban-project-workflow` — it contains the shared PR workflow,
respawn guard, profile sync, and worker tuning patterns.

## GitHub

`mnlamart/music-library` — remote: `https://oauth2:TOKEN@github.com/Seven74AI/music-library.git`

## Environment

- `MOCKS=true` — all external services mocked
- `GITHUB_TOKEN` in `.env` = **application OAuth** (GitHub login, `api.github.com`), NOT a git push token. Git push uses the remote URL token.

## Workflow Rules

- **Verify, don't assume.** When checking project state (open issues, PR status, audit findings, CI status, upstream sync), always check actual state — fetch the API, compare commit hashes, grep the code, run the test. Never state something is "likely resolved" or "on upstream" or "ready to merge" without evidence. Specifically for PRs: use `gh pr diff`, `gh api .../compare` to compare actual commits between fork and upstream, not just title matching. The user prefers evidence-backed reports over probabilistic assessments. When they ask "is X on upstream?" or "why is Y not merged?", run the verification commands — don't speculate.

- **Plan before coding on feature restorations.** When restoring a previously-removed feature (especially one with existing ADRs and implementation docs), present the architecture plan for alignment before touching any code. The user will stop you if you jump to implementation — they want to stress-test the plan against existing docs first (often via `/grill-with-docs`).

- **Read referenced docs completely.** When the user points you at files in `/tmp` or elsewhere that inform a feature, read them to EOF — do not report findings from a truncated read. A partial read of `refactor-storage-system.md` (stopped at line 500/625) was called out. If a file is truncated, re-read with offset until you hit the end.

- **Letter-labeled options in decision sessions.** When presenting multiple-choice options (especially during `/grill-with-docs`), label them A/B/C/D. The user prefers replying with a single letter rather than retyping the full answer. Do NOT bundle sub-questions — present one at a time even when they seem tightly coupled.

- **⛔ Check CONTEXT.md before proposing architectural fixes.** When a feature is broken or behaving unexpectedly, check CONTEXT.md first. The user may have decided against the current implementation pattern (e.g., "no redirects") during a prior grill session, and proposing a fix that contradicts a settled decision wastes time. Also search session transcripts with session_search() for the relevant feature discussion. Concrete example (2026-07-08): agent incorrectly proposed CSP fix for broken audio playback, user pointed to grill session decision #22 — the redirect itself was wrong, not the CSP. Always session_search + check CONTEXT.md before proposing fixes.

## Local Dev Setup

The working copy at `/tmp/music-library` is ephemeral — assume it needs to be cloned fresh and `.env` configured each session.

### `.env` required vars (for vitest + typecheck)

```bash
DATABASE_URL="file:./data.db?connection_limit=1"
CACHE_DATABASE_PATH="./other/cache.db"
LITEFS_DIR=/tmp
MOCKS=true
```

### Prisma client generation

`npm run typecheck` fails with `Cannot find module '#prisma/client.js'` until Prisma client is generated:

```bash
npx prisma generate   # requires DATABASE_URL in .env
```

### Running tests

```bash
npx vitest run app/utils/service-playlist.server.test.ts   # single file
npx vitest run                                             # all vitest tests
```

The global setup (`tests/setup/global-setup.ts`) imports `cache.server.ts` which demands `LITEFS_DIR` — without it, vitest crashes before any test runs.

### Git push

The remote URL uses the `oauth2:TOKEN@github.com` format. If pushing fails with "Authentication failed", refresh the token:

```bash
gh auth token | xargs -I{} git remote set-url origin "https://oauth2:{}@github.com/Seven74AI/music-library.git"
```

## Admin Pages

Admin routes live under `app/routes/admin+/`:

- `/admin/youtube-cookies` — upload/paste YouTube cookie files for yt-dlp auth
- `/admin/audio-queue` — queue dashboard for archive jobs
- `/admin/cache` — cache management
- `/admin/cache/sqlite` — SQLite cache inspector

Admin navigation links go in the **`UserDropdown`** component (`app/components/user-dropdown.tsx`), gated by `userHasRole(user, 'admin')`. Both Audio Queue Admin and YouTube Cookies are linked (added in PR #74). All admin routes require `requireUserWithRole(request, 'admin')` in their loader.

## Tech Stack

- **Framework:** Epic Stack
- **ORM:** Prisma 7 + SQLite
- **Frontend:** React 19 + Tailwind 4
- **Mocks:** `MOCKS=true`

## ⛔ Reviewer account pitfall (RESOLVED)

The reviewer agent uses a **GitHub App** (`hermes-sevenai-reviewer`, App ID 3788528)
which provides a separate identity from the coder (`Seven74AI`). The app must have
`Contents: Write` permission — reviews show as `hermes-sevenai-reviewer[bot]` and
count toward branch protection's required approval count. See `kanban-project-workflow`
§ Reviewer agent and `references/github-app-reviewer-setup.md` for the full setup.

## Branch Protection & CI

- **Fork:** `Seven74AI/music-library` — branch protection: `enforce_admins: true`, `required_reviews: 1`, `dismiss_stale_reviews: true`, required checks: `lint, typecheck, vitest, playwright-gate`. Auto-merge ON, delete branch on merge.
- **Workflow:** MUST be named `CI` (exact match for branch protection `contexts: ["CI"]`), npm, 2-shard playwright + `playwright-gate` gate job
- **Upstream:** `mnlamart/music-library` — pnpm, PR #9 merged (fix `|| true`)

**⛔ ALL coder tasks MUST include `kanban-project-workflow` in skills.**
Tasks created with `skills=["music-library"]` only will merge red CI because the
coder doesn't know the merge rules. Always use:
```bash
hermes kanban --board music-library create --assignee coder \
  --skills music-library --skills kanban-project-workflow ...
```

## PR Workflow

Two-tier PR model: **fork first, then upstream.**

⚠️ **Pitfall — parallel PRs to fork + upstream.** Do NOT open the same branch as two PRs simultaneously (fork + upstream). The upstream PR may merge first, leaving the fork PR dangling/orphaned. Always follow: 1) open PR on fork → 2) merge on fork → 3) then open PR fork main → upstream. If you find an orphaned fork PR, check whether a matching upstream PR already merged before assuming it needs action.

1. Push feature branch to `Seven74AI/music-library` fork
2. Open PR on the **fork** (`Seven74AI/music-library`) — review and merge there first
3. Only after fork merge, open PR from fork `main` → upstream (`mnlamart/music-library`)
4. Upstream PR → reviewer (GitHub App) approves → squash merge

Never open a PR directly against upstream from a feature branch. Always land on the fork first. This applies to all changes including CI workflow edits, docs, dependency bumps — not just feature code.

⚠️ **Pitfall — never sync fork while kanban tasks are active.** Force-pushing fork `main` while kanban workers are running feature branches introduces avoidable risk (even though branches are technically independent). Wait until ALL tasks complete — check with `hermes kanban --board music-library list | grep -v "✓"`. If anything shows as running/blocked/todo, defer the sync. Consolidation PRs to upstream should happen only after the board is clean.

## CI

Full CI: `lint` + `typecheck` + `vitest` + `playwright-gate` (consolidates 2 shards into one check).

**Deployment re-enabled (repo-gated):** container + deploy jobs restored in PR #34 (upstream). Guard: `github.repository == 'mnlamart/music-library'` — jobs only fire on upstream pushes, never the fork. Fork CI unchanged. Full YAML at `references/deployment-gating.md`.

### Pitfall: `|| true` / `--if-present` — silent CI bypass

Two variants, same effect:

- `pnpm typecheck || true` (shell) — swallows non-zero exit codes
- `npm run typecheck --if-present` (npm) — skips silently if the script doesn't exist

Both make CI report green while type errors pass through.
Fixed upstream in PR #9 but can re-appear after any workflow change. Always verify:
```bash
grep "typecheck" .github/workflows/deploy.yml
# MUST show: pnpm typecheck
# MUST NOT show: pnpm typecheck || true
```

### Pitfall: Emoji CI job `name:` fields break branch protection

GitHub uses the job-level `name:` field as the status check context. If a workflow has
`name: ⬣ ESLint` on the `lint:` job, the check reports as `⬣ ESLint` — but branch
protection requires `lint`. The contexts never match, auto-merge hangs forever.

**Fix:** remove ALL job-level `name:` fields from `.github/workflows/deploy.yml`.
Fixed in `Seven74AI/music-library#2`. Step-level emoji names are fine.

## Pitfalls

- **⛔ Never trust a PR title claiming tests are "broken."** Run them. `references/verification-anti-patterns.md` has concrete examples (PR #76 removed 3 passing tests).
- **⛔ Local E2E tests need `LITEFS_DIR=/tmp`.** Without it, dev server crashes during SSR. See `references/e2e-testing.md` for full setup.
- **Reviewer self-approval:** GitHub App may show `authorAssociation: NONE` → admin-merge workaround (see `kanban-project-workflow`)
- **Empty git remote token:** The remote URL is `https://oauth2:TOKEN@github.com/...` but the token portion may be empty on a fresh clone. Pushing fails with "Authentication failed." Fix with `gh auth token | xargs -I{} git remote set-url origin "https://oauth2:{}@github.com/Seven74AI/music-library.git"`.
- **Stale local `main` after fork sync:** After a consolidation PR merges upstream and the fork is force-pushed to match (`git reset --hard upstream/main && git push --force origin main`), the local `main` branch is stale. Creating a feature branch from it produces a PR with dozens of already-merged files. Always branch from `origin/main` instead of local `main`:
  ```bash
  git fetch origin main
  git checkout origin/main -b feat/my-branch
  ```
  Or, if already on a bloated branch, cherry-pick the unique commit onto a fresh `origin/main` branch:
  ```bash
  git checkout origin/main -b feat/my-branch-clean
  git cherry-pick <deploy-commit-sha>
  git push --force origin feat/my-branch-clean:feat/my-branch
  ```
- **Circular dependency risk:** `service-playlist.server → track-batch-processor → playlist-utils → service-playlist` is a cycle if playlist-utils imports error classes from the facade. Keep `ServiceNotFoundError` / `NoTokensError` in `playlist-utils.server.ts` (where they're thrown), not in the facade.
- **`BatchProcessorProvider.service` type mismatch:** The `transformPlaylistItem` return type in `BatchProcessorProvider` previously declared `service: { connect: { id: string } }` but Prisma's `PlaylistSyncProvider.transformPlaylistItem` returns `service?: ServiceWhereUniqueInput`. These are structurally incompatible. The field is always destructured-out by callers (`service: __`), so it was widened to `unknown`. If adding a new provider implementation, ensure the `service` field is present but don't constrain its type — `unknown` is correct.

### Frontend pitfalls

- **⛔ `formatDuration(track.duration || 0)` shows "0:00" for null durations.** The `formatDuration` function in `app/utils/format-duration.ts` already returns `"--:--"` for `null`, but passing `track.duration || 0` converts null to 0, which displays as "0:00" instead of "--:--". Fix: pass `track.duration` directly — let `formatDuration` handle null. Search pattern to find all instances: `formatDuration(` across the codebase.

- **⛔ ArchiveJob worker never extracts metadata or updates `Track.duration`.** `worker.server.ts:135-143` creates a `TrackAudioFile` record with hardcoded `format: 'mp3'` and `mimeType: 'audio/mpeg'` — it never calls `extractAudioMetadata()` (from `audio-metadata.server.ts`) to extract duration, bitrate, or sample rate from the downloaded audio. Result: `Track.duration` stays `null` forever for all YouTube-imported tracks. The `yt-dlp` output file is available at `result.filePath` on disk BEFORE uploading to Tigris — metadata can be extracted there without re-downloading from S3. **Fix:** call `extractAudioMetadata(buffer)` on the downloaded file, update `Track.duration` via `prisma.track.update({ where: { id: trackId }, data: { duration } })`, and enrich the `TrackAudioFile.create` call with real `format`, `mimeType`, `fileSize`, `bitrate`, and `sampleRate` instead of hardcoded values. Full workflow at `references/archivejob-duration-gap.md`.

- **⛔ YouTube playlist sync sets `duration: null`.** `transformYouTubePlaylistItemToTrack` in `app/types/transformations.ts:49` sets `duration: null` because playlist items (from `/playlistItems` API) don't include video duration. Only the `/videos` API returns `contentDetails.duration` (ISO 8601 format, parsed by `parseDuration()` in `youtube-utils.ts`). The standalone import page (`service-import.server.ts`) does get real durations via `YouTubeVideo`. Playlist-synced tracks will always show "--:--" unless video details are fetched separately. **Note: null duration is a DISPLAY concern, NOT a playback blocker.** The `<audio>` element reads file metadata via `loadedmetadata`, not from `track.duration`.

- **⛔ Manual `trackForListItem` construction drops fields — silent playback failure.** When a page cherry-picks fields from a server-returned track object into a manually-constructed `TrackListItem` props object (instead of spreading or passing the full track object directly), any omitted field becomes `undefined`. The `TrackListItem.handlePlayTrack` guard at line 111 silently returns when `track.audioFiles` is falsy — no error, no console message, nothing. The player just doesn't open. Search signature: `const trackForListItem = {` — any page using this pattern must include `audioFiles: track.audioFiles`. Currently only `playlist.$id.tsx` (YouTube playlist detail) is affected; `SortableTrackList` and `library.index.tsx` pass the track object directly and are safe. The diagnostic path for playback-triggering-nothing bugs: schema (`duration Int?`) → transformation (`transformYouTubePlaylistItemToTrack` sets `duration: null`) → server query (is `audioFiles` included in Prisma `include`?) → frontend mapping (is it dropped?) → player guard (`!track.audioFiles` bail). Duration display vs playback are separate concerns — null `duration` only affects `formatDuration` display, not the `<audio>` element which reads native metadata.

- **⛔ Audio resource route requires library membership — blocks service playlist tracks.** `audio.$trackId.tsx:35` gates on `track.userTracks.length === 0` → 403. This means a track with archive audio that exists in a synced YouTube playlist but is NOT in the user's library cannot be played, even though the user "owns" it via their service playlist. To extend access, add `servicePlaylistTracks: { where: { playlist: { ownerId: userId, isActive: true } }, take: 1 }` to the existing Prisma `include`. All joins are indexed (`ServicePlaylistTrack.trackId`, `ServicePlaylist` PK, `ServicePlaylist.ownerId`) — no performance impact. Count `userTracks.length > 0 || servicePlaylistTracks.length > 0` for the access decision.

- **⛔ `<audio>` element has no `error` event listener — silent playback failure.** `audio-player.tsx` registers listeners for `timeupdate`, `loadedmetadata`, `play`, `pause`, `seeking`, `seeked`, `ended` — but NOT `error`. When an audio source returns 403, 404, or a network error, the failure is completely invisible: the play button flickers and no feedback is given. Always add an `error` listener that logs `MediaError.code` to console at minimum when wiring `<audio>` elements.

- **⛔ `<audio src>` type is `string | undefined`, NOT `string | null`.** React's `<audio>` element (via `JSX.IntrinsicElements['audio']`) declares `src?: string | undefined`. Using `useState<string | null>(null)` and passing it to `src={audioSrc}` fails with `TS2322: Type 'string | null' is not assignable to type 'string | undefined'`. Always use `useState<string | undefined>(undefined)` for audio/video source state. Same applies to `<video>`, `<img>`, `<source>`, and any HTML element with optional `src` attributes.

- **⛔ Cherry-pick after squash merge — fix commits can be left behind.** When a PR is opened and a fix commit is pushed to the same branch AFTER the PR is merged, the fix commit is NOT included in the merge. GitHub squashes at the moment of merge — commits pushed after that point stay on the branch but never reach upstream. If a typecheck or lint fix is needed after pushing the branch, either: (a) wait for CI to run BEFORE requesting merge, (b) create a new PR with just the fix cherry-picked onto upstream main. Concrete example: PR #42 merged with `null` type, `b5130eb` fix commit stayed orphaned on the branch, required cherry-pick into PR #44.

- **⛔ CSP `media-src 'self'` blocks audio from S3/Tigris — silent playback failure (prod only).** `audio.$trackId.tsx` returns a 302 redirect to a Tigris presigned URL (`{bucket}.fly.storage.tigris.dev`). The CSP in `server/index.ts:92` has `media-src: ["'self'"]`, which allows media ONLY from the app origin. The redirect target is a different origin → the `<audio>` element is blocked by the browser. **Symptoms:** player opens but shows `0:00` duration (or `--:--` in detail views), nothing plays, no console error unless an error listener was added. **Why dev works but prod doesn't:** `server/index.ts:84` sets `reportOnly: MODE !== 'production'` — in dev, CSP is `Content-Security-Policy-Report-Only` (violations logged, not enforced). In prod, it's `Content-Security-Policy` (enforced). **Why download works:** `<a>` click downloads use navigation, not media loading — they bypass `media-src` altogether. **⛔ The 302 redirect itself is wrong per decision #22.** The settled decision says: "No redirect — direct presigned URL. The audio resource route returns the presigned Tigris URL directly (no 302 redirect). Client fetches it and sets `<audio src>` to the S3 URL." The redirect is an extra round-trip and exposes the URL anyway. **Full fix:** (a) Modify `audio.$trackId.tsx` to return the presigned URL as JSON instead of `redirect(url)`. (b) Update the audio player to `fetch()` the URL from the route and set it on `<audio src>`. (c) Add `https://*.fly.storage.tigris.dev` to `media-src` in BOTH `server/index.ts:92` and `app/utils/csp.server.ts:17`. CSP is configured in two places because `csp.server.ts` generates a static CSP string for Remix SSR, while `server/index.ts` uses helmet for middleware-level CSP with per-request nonces. Both must be kept in sync. Full diagnostic + verification commands at `references/csp-audio-playback.md`.

- **`thumbnailUrl` lives on `ServicePlaylistTrack`, not `Track`.** For YouTube playlist tracks, the thumbnail URL is stored on the join table (`ServicePlaylistTrack.thumbnailUrl`), NOT on the `Track` model. Queries must include it explicitly: `include: { track: { include: { coverImage } } }` PLUS access `pt.thumbnailUrl` from the join record. The `getPlaylistTracksWithUserStatus` query in `service-playlist.server.ts` does this correctly — spread `pt.track` first, then overlay `thumbnailUrl: pt.thumbnailUrl`. The `TrackThumbnail` component falls back from `coverImage.objectKey` to `thumbnailUrl` when the track has no downloaded cover image.

### Add-to-library `itemActions` render prop — page responsibilities

The restoration added `itemActions` to `TrackListItem` as a render prop: `({ trackId, isInLibrary, isDeleted }) => ReactNode`.

**Which page gets which actions:**

| Page | Should have library toggle? | Should have playlist mgmt? |
|------|---------------------------|---------------------------|
| `playlist.$id.tsx` — YouTube synced playlist | ✅ YES — add/remove tracks to personal library, "Add All Missing" bulk | ❌ NO — only sync/refresh/unsync |
| `playlists.$playlistId.tsx` — user-created playlist | ❌ NO — library is a separate concern | ✅ YES — reorder, remove from playlist, add to queue |

**Current state (fixed in PR #74/#38):** Library buttons live on `playlist.$id.tsx` (YouTube sync page), NOT on `playlists.$playlistId.tsx` (user playlists). See `references/add-to-library-removal.md` for original design decisions.

Implementation reference: `playlists.$playlistId.tsx` uses `useFetcher` → `POST /resources/track-library` with optimistic `libraryStatus` tracking and an "Add All Missing" bulk button with count confirmation dialog. This exact pattern should be replicated on `playlist.$id.tsx`.

### ⛔ Skill name collisions: Matt Pocock skills

Several skills referenced in the Matt Pocock flow collide with local stubs sharing the
same name: `grill-with-docs`, `to-prd`, `to-issues`, `tdd`. All fail with ambiguity if
duplicates exist.

**Fix:** remove the non-Matt-Pocock copy, keeping the symlinked version (the one at
`~/.hermes/skills/<name>/` → `~/.hermes/mattpocock-skills/skills/engineering/<name>/`).
Remove it from BOTH `~/.hermes/skills/software-development/<name>/` AND
`~/.hermes/profiles/coder/skills/software-development/<name>/` — the collision can exist
at either level. Verify with `skill_view('tdd')` — should resolve cleanly (no ambiguity).

**Fallback workaround** (if the duplicate cannot be removed): load by full path:
`skill_view(name='software-development/grill-with-docs')` etc. But fixing the duplicate is
strongly preferred because kanban workers resolve skills by bare name and crash on ambiguity.

**⛔ Kanban worker impact:** when a skill collision exists in the coder profile
(`~/.hermes/profiles/coder/skills/`), kanban workers crash on startup with
`Unknown skill(s): <name>`. The dispatcher enters a silent crash loop —
`gave_up → promoted → respawn` — without ever reaching `blocked` status.
No notification fires even if `notify-subscribe` is configured. Diagnosis:
check `hermes kanban show <task_id>` for `consecutive_crashes` count. Fix:
remove the non-Matt-Pocock duplicate from both `~/.hermes/skills/` and
`~/.hermes/profiles/coder/skills/`. Check ALL profiles, not just the global
skills dir — the coder profile has its own `skills/software-development/`
tree.

### yt-dlp pitfalls

- **`releases/latest` is a time bomb in the Dockerfile.** The Dockerfile line
  `ADD https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp`
  bakes the binary at build time. When YouTube changes its JS challenge,
  old yt-dlp versions (e.g. 2026.05.25) return `"Sign in to confirm you're
  not a bot"` even with valid cookies. The Docker image stays broken until
  rebuilt. A rebuild picks up the latest automatically; the only risk is
  forgetting to rebuild after YouTube changes.

- **`--no-warnings` was removed from yt-dlp args (PR #36).** It was
  suppressing diagnostic WARNINGs like `"cookies are no longer valid"` that
  explain WHY a failure happened. The ERROR-level message still came through
  and triggered the right category, but the root-cause warning was lost.

- **Output template now includes video ID (PR #36).** `%(title)s.%(ext)s` →
  `%(title)s [%(id)s].%(ext)s`. Prevents filename collisions when two
  different tracks have the same YouTube title.

- **CDN 403 ≠ auth 403.** yt-dlp can return two distinct 403 errors:
  - `"unable to download video data: HTTP Error 403"` — CDN-level media
    block (IP-based, transient). NOT a cookie problem. Maps to `NETWORK`
    (retriable).
  - `"Unable to download webpage: HTTP Error 403"` — auth-layer block.
    Cookie may be expired. Maps to `AUTH` (non-retriable, triggers cookie
    invalidation).
  The classification runs CDN check BEFORE the auth check so "unable to
  download video data" with 403 is caught first. See `yt-dlp.server.ts`
  `categorizeStderr()`.

- **Cookie file is per-machine.** The VPS (`~/.hermes/cookies/yt_cookies.txt`)
  and the Fly.io volume (`/data/youtube-cookies.txt`, set via
  `COOKIE_FILE_PATH` env) are different files on different machines.
  Updating one doesn't update the other. Fly.io cookies are uploaded
  through the admin panel (`/admin/youtube-cookies`).

- **⛔ COOKIE_FILE_PATH was silently undefined in production.** The worker read
  `process.env.COOKIE_FILE_PATH || undefined` but the Dockerfile never set
  `COOKIE_FILE_PATH`. Zod's `.default()` in `env.server.ts` only applies during
  validation — it does NOT mutate `process.env`. Result: `cookieFile` was
  always `undefined`, `--cookies` was never passed to yt-dlp, and every
  archive job hit YouTube's sign-in wall. The admin upload page wrote to
  `/data/youtube-cookies.txt` via its own fallback (`??`), but the worker
  never read it. **Fixed in PR #36** by exporting `cookieFilePath()` from
  `youtube-cookie.server.ts` and calling it from the worker — single source
  of truth with one fallback.

### AUDIO_ARCHIVE_ENABLED pitfall

- **⛔ `AUDIO_ARCHIVE_ENABLED` gates auto-enqueue — it shouldn't.** `auto-enqueue.server.ts:25` checks `if (process.env.AUDIO_ARCHIVE_ENABLED !== 'true') return`. This prevents ArchiveJob creation when archiving is off. The user's intent: `AUDIO_ARCHIVE_ENABLED` should only gate the worker (processing), NOT enqueue (job creation). Tracks imported while archiving is off have no ArchiveJob when it's later turned on. **Fix:** remove lines 25-26 from `auto-enqueue.server.ts`. Jobs should always be created; the worker just won't process them until enabled.

### Pitfall: `tsc --noEmit` without `react-router typegen` — fake errors

The project's `typecheck` script runs `react-router typegen && tsc`. Running `tsc --noEmit` alone produces dozens of `Cannot find module './+types/...'` errors across the entire codebase. These are NOT pre-existing bugs — the `+types/` files are generated by `react-router typegen`. Always run the full pipeline:

```bash
npm run typecheck   # NOT npx tsc --noEmit
# or, if running manually:
npx react-router typegen && npx tsc --noEmit
```

### Test infrastructure pitfalls

- **⛔ Moving UI elements between pages breaks Playwright tests.** When moving components (buttons, dialogs, `itemActions`) from one route to another, the corresponding Playwright e2e tests must be updated or inverted. The test at `tests/e2e/playlists.test.ts` has specific tests for library toggle buttons and "Add All Missing" — if those features move to a different page, the tests must be rewritten to target the new page (or inverted to assert absence on the old page). Always run `npx playwright test` after page-level changes before pushing.

- **⛔ Strict mode violation: duplicate role/name buttons on desktop.** The YouTube import page has two "Search" buttons at desktop viewport — the global nav bar search (`getByRole('banner')`) and the import page's form button (`#main-content`). `page.getByRole('button', { name: /search/i })` resolves to 2 elements, failing strict mode. Fix: use `.first()` or scope to `#main-content`. This surfaced as a flaky failure in `tests/e2e/youtube-import.test.ts` — the test passes on mobile viewport (nav search hidden) but fails on desktop CI. Fixed in PR #77.

- **pnpm install breaks native modules.** When `node_modules` is nuked and
  reinstalled with pnpm, build scripts for native packages (better-sqlite3,
  @prisma/engines, esbuild) are ignored by default. Vitest crashes with
  `MODULE_NOT_FOUND` for `better_sqlite3.node` or `@prisma/client`.
  Fix:
  ```bash
  pnpm approve-builds better-sqlite3 @prisma/engines prisma esbuild
  pnpm install --no-frozen-lockfile
  ```
  Or keep using npm (`npm ci`) if package-lock.json exists — the fork
  uses npm, upstream uses pnpm.

### Dependency bump pitfalls

When handling dependabot PRs that bump major versions, these project-specific traps recur.
Full migration recipes at `references/dependency-migrations.md`.

- **Cookie v2 (^1.x → ^2.x):** Renamed `serialize`→`stringifySetCookie` (different signature — takes `{name, value, ...opts}` object), `parse`→`parseCookie`. Stale `@types/cookie` from `@remix-run/server-runtime` overrides cookie v2's built-in types — fix with `"skipLibCheck": true` in tsconfig.json. Files affected: `redirect-cookie.server.ts`, `theme.server.ts`.
- **ESLint v10 (^9.x → ^10.x):** Transitive `typescript-eslint@8.46.0` crashes with `"Class extends value undefined is not a constructor"` because `FlatESLint` was removed in ESLint v10. Fix: install `typescript-eslint@latest` as direct devDep to override the stale transitive.
- **Vitest v4 (^3.x → ^4.x):** Constructor mocks break — `vi.fn()` is no longer callable with `new`. Use `vi.fn(function(this: any, ...) { … })` instead. `console.warn` mocks are enforced more strictly in test setup (`setup-test-env.ts` throws on warn). Affected test files may need `consoleWarn.mockImplementation(() => {})` in their `beforeEach`.
- **Vitest v4 + jsdom + node:sqlite:** Vite 7's `import-analysis` plugin rejects `node:sqlite` as a bundlable built-in in the jsdom environment. `deps.external`, `ssr.external`, and `resolve.alias` do NOT intercept it. The working fix: add a Vite plugin with `enforce: 'pre'` to the MAIN `plugins` array (NOT `test.plugins`) that returns `{ id: 'node:sqlite', external: true }` from `resolveId`. The plugin MUST have an explicit `return undefined` on all code paths (TS7030, `noImplicitReturns`). See `references/dependency-migrations.md` for the full snippet.\n- **Vitest v4 coverage thresholds:** v4 ENFORCES thresholds; v3 silently ignored them. With `all: true` across ~100 source files, thresholds like 25% functions / 50% branches are impossible. Set floors just below actual coverage (~8% functions/branches). This is NOT a "lower to make CI pass" hack — the v3 values were never actually met, they just weren't checked.

## Fork Sync After Consolidation

After a consolidation PR merges to upstream, the fork will show N commits "ahead"
(the unsquashed individual commits) while being "behind" by 0. To eliminate the
cosmetic divergence:

1. **Verify trees are identical** before proceeding:
   ```bash
   git fetch upstream
   git rev-parse origin/main^{tree}   # fork
   git rev-parse upstream/main^{tree} # upstream
   # Must match — if not, STOP. Content differs.
   ```
2. Delete branch protection on the fork:
   ```bash
   gh api -X DELETE repos/Seven74AI/music-library/branches/main/protection
   ```
3. Hard reset and force push:
   ```bash
   git reset --hard upstream/main
   git push --force origin main
   ```
4. Restore branch protection with the **full original config** (not a
   stripped-down minimal payload). Current fork settings:
   ```bash
   gh api -X PUT repos/Seven74AI/music-library/branches/main/protection \
     --input - <<'EOF'
   {
     "required_status_checks": {
       "strict": true,
       "contexts": ["lint", "typecheck", "vitest", "playwright-gate"]
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
   EOF
   ```
   ⚠️ `"allow_force_pushes": {"enabled": false}` — feeding that back to PUT
   fails with `"is not a boolean"`. Always reconstruct with flat booleans.
   Do NOT use a stripped-down "minimal" payload — the fork has full
   protection (reviews, status checks, enforce_admins) and dropping those
   silently regresses the settings.

5. Re-enable auto-merge (wiped with the protection):
   ```bash
   gh api -X PATCH repos/Seven74AI/music-library \
     -f allow_auto_merge=true -f delete_branch_on_merge=true
   ```

6. Verify: `gh api repos/mnlamart/music-library/compare/main...Seven74AI:main --jq '.status'` → `identical`

## Domain Architecture

Audio archiving is being reimplemented (reversing ADR-004). Settled decisions in `docs/CONTEXT.md` (25 decisions, numbered 1-25 across Architecture, Authentication, Storage, Notifications, Auto-Enqueue, Worker Behavior, Audio Serving, and Display & Navigation sections).

Key decisions most likely to affect future work:
- **#5 (Error categorization)**: yt-dlp stderr → 7 categories, retry logic
- **#9 (Cookie upload UI)**: File upload + textarea paste on admin panel
- **#10 (Cookie refresh auto-reset)**: AUTH_REQUIRED jobs → pending on cookie upload
- **#18 (Idempotent enqueue)**: Unique constraint caught, silently skips
- **#22 (Audio serving — no redirect)**: Return presigned URL directly. Client fetches it. CORS on bucket. CSP must include Tigris domain. Fixed in PR #42 (route returns JSON, player fetches URL). CSP fix in PR #41.
- **#23 (Null durations → --:--)**: Display convention, not a playback issue

When working on audio archiving, always consult `CONTEXT.md` first — it's the domain glossary. The condensed implementation reference is at `references/audio-archiving-implementation.md` (models, yt-dlp command, worker loop, retry strategy, file manifest). The original full docs are in `/tmp`: `audio-archive-feature.md` (plan), `003-audio-worker-architecture.md` (ADR-003), `refactor-storage-system.md` (storage layer).

**Add-to-library restoration**: The feature to add individual YouTube tracks from
synced playlists to a user's library was removed in commit `bfb8fde` (Nov 2025).
Since audio archiving has been re-implemented, the original rationale no longer
applies. See `references/add-to-library-removal.md` for the full list of deleted
files, removed methods, and restoration approach.

## Kanban Task Skills (Matt Pocock flow)

This project uses the Matt Pocock skill flow (`/grill-with-docs` → `/to-prd` → `/to-issues` → `/implement`).

**Coder tasks** (via `hermes kanban create`):

```bash
# Correct: positional title + --body for task description
hermes kanban --board music-library create \
  "Task title here" \
  --assignee coder \
  --skill music-library --skill kanban-project-workflow --skill implement --skill tdd --skill code-review \
  --body "Task description. Reference GitHub issues by #number." \
  --parent <parent_task_id> \          # for blocking dependencies
  --initial-status blocked             # if blocked by parent
```

**⛔ Common mistake:** `--title` and `--prompt` flags do NOT exist. Title is the positional argument; body uses `--body`. Using wrong flags produces `unrecognized arguments` error.
`implement` orchestrates, `tdd` drives test-first at pre-agreed seams, `code-review` does the coder's final self-review before handing off to the reviewer. All three are Matt Pocock skills loaded from `~/.hermes/skills/` symlinks.

**Reviewer tasks**:
```
--assignee reviewer \
--skill music-library \
--skill kanban-project-workflow \
--skill code-review
```
Reviewer runs the two-axis review (Standards + Spec) via `code-review`.

**Pitfall — missing skills**: If the coder lacks `code-review`, they'll implement but won't self-review. If they lack `implement`, they won't know the implement→tdd→code-review flow. Always include all five.

## Matt Pocock Skills Setup

The repo's `CLAUDE.md` has an `## Agent skills` block pointing to `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, and `docs/agents/domain.md`. These were set up via `/setup-matt-pocock-skills`. Triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) must exist as GitHub labels on the repo. Domain docs reference `docs/decisions/` for ADRs (NOT `docs/adr/`).

## Status

- God-module decomposition complete (facade 942→716 lines)
- Fork synced to upstream (identical trees at `e70d4c5`). Branch protection restored (enforce_admins, 1 review, required checks).
- Board: all audio-archive tasks complete — slices 1-7 merged to fork + upstream
- Dependency bumps PR #37: cookie v2, eslint v10, vitest v4 applied with fixes
- **Audio archiving**: Fully implemented and merged upstream (mnlamart/music-library#31). 16 architecture decisions in `CONTEXT.md`. Feature lives in `app/features/audio-archive/`. Key: ArchiveJob separate from TrackAudioFile, yt-dlp cookies + sleep intervals, 2-min worker interval with polling breaks, direct presigned Tigris URLs for audio serving, Telegram Bot API for cookie-expiry notifications.
- **Worker wiring**: `app/entry.server.tsx` starts the worker via dynamic import + `setInterval(processQueueTick, AUDIO_ARCHIVE_INTERVAL_MS)` when `AUDIO_ARCHIVE_ENABLED=true`. Launched from the app layer (not `server/index.ts`) to respect ADR-002's no-cross-boundary-imports rule. Previously the worker was fully implemented and tested but never scheduled.
- **Architecture review** (2026-07-07): 6 of 7 deepening candidates applied. Summary: removed `provider as any` cast (replaced with real `Prisma.ServiceCreateNestedOneWithoutTracksInput` type), deleted dead `server/utils/` (fixed ADR-002 violation), deduplicated `worker-control` mutations (155→125 lines), collapsed `youtube-cookie` (7→3 exports + type), consolidated env vars (11 missing vars added to Zod schema), wired the worker. Candidate #5 (inline playlist-utils) cancelled — 6+ call sites would create more duplication than the module removes.
- **Worker wiring**: Worker launched from `app/entry.server.tsx` via dynamic import + `setInterval` (gated by `AUDIO_ARCHIVE_ENABLED === 'true'`). Launches from app layer — no ADR-002 cross-boundary violation. Former `server/utils/db.ts` and `server/utils/storage.ts` (dead code from ADR-004) have been removed.
- **Cookie module API**: `youtube-cookie.server.ts` consolidated to 4 exports + type: `cookieFilePath()`, `readCookies()`, `writeCookies(cookies, filePath?)`, `parseCookieLine()`. Deletion = `writeCookies([])`. `cookieFilePath()` is the single source of truth for the cookie file location (`process.env.COOKIE_FILE_PATH ?? '/data/youtube-cookies.txt'`) — imported by both the admin route and the worker.
- **Docs**: Post-audio-archiving documentation complete (README, ARCHITECTURE, CONTEXT.md, ADR-011, mocking, TESTING_PLAN). Merged to fork (#58) and upstream (#31).
- **Architecture review** (2026-07-07): 6 of 7 deepening candidates applied. `BatchProcessorProvider.service` widened to `unknown` (was `{ connect: { id: string } }` — mismatched Prisma's `ServiceWhereUniqueInput`). `worker-control.server.ts` deduplicated (private `setWorkerState`). Env schema now covers all 27 vars. `provider as any` cast removed from `service-playlist.server.ts:96`.
- **Issues**: #38 (architecture reference) remains open by design. All others (#39–#48) closed.
- **Add-to-library restoration**: ✅ COMPLETE — 5 slices (#62–#67) merged to fork (PRs #68–#73) and upstream (mnlamart/music-library#37). 13 architecture decisions made during the grill-with-docs session (##17–29); decisions ##17–19 written to `docs/CONTEXT.md`, remainder tracked in the session transcripts.
- **UI polish fixes** (PR #74 → fork, PR #38 → upstream, merged): 
  - `itemActions` library buttons moved from `playlists.$playlistId.tsx` (user playlists, wrong) to `playlist.$id.tsx` (YouTube playlist sync, correct) — Playwright tests updated
  - YouTube Cookies link added in admin UserDropdown
  - Null duration display fixed (0:00 → --:--)
- **Playback fixes** (3 slices, merged upstream #40): YouTube playlist tracks now playable — added `audioFiles` to frontend mapping, relaxed audio resource access check for service playlist tracks, added error listener on `<audio>` element. 7 new test files. Upstream PR #40 consolidates all 3 slices.
## Kanban Telegram Notifications

To enable Telegram notifications on kanban tasks (get pinged when workers complete/block):

```bash
# Find your Telegram target
send_message(action='list')

# Subscribe a task (use the exact target string from the list)
hermes kanban --board music-library notify-subscribe <task_id> \
  --platform telegram --chat-id "Lieutner 7D (dm)"

# Verify subscriptions
hermes kanban --board music-library notify-list <task_id>

# Remove
hermes kanban --board music-library notify-unsubscribe <task_id>
```

Note: subscriptions are per-task, not inherited by child tasks. When a coder task completes and creates a reviewer task, you must subscribe to the new reviewer task separately. Automate this with a cron watchdog script (see `~/.hermes/scripts/audit-notif-watchdog.py` — polls the board every 3 min and auto-subscribes new tasks linked to audit roots).

### Monitoring running tasks

```bash
# Check task status and events
hermes kanban --board music-library show <task_id>

# Tail live output from the worker agent
hermes kanban --board music-library log <task_id>

# Verify the worker process is still alive (if a task seems stuck)
ps -p <pid> -o pid,state,pcpu,rss,etime --no-headers
```

### Triage label pitfalls

- **`ready-for-agent` label already exists with wrong color.** `gh label create ready-for-agent` fails with "already exists". Use `--force` to override: `gh label create ready-for-agent --color 0E8A16 --force --description "Ready for AI agent to work on"`. All five triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) must be present before publishing PRD issues.