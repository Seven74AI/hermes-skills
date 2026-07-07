---
name: music-library
description: "Music Library project configuration — tech stack, repo, tenant."
version: 1.5.0
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

- **Verify, don't assume.** When checking project state (open issues, audit findings, CI status), always check the actual state of the codebase and run verification commands. Never state something is "likely resolved" without evidence — fetch the issue, grep the code, run the test, check the file. The user prefers evidence-backed reports over probabilistic assessments.

- **Plan before coding on feature restorations.** When restoring a previously-removed feature (especially one with existing ADRs and implementation docs), present the architecture plan for alignment before touching any code. The user will stop you if you jump to implementation — they want to stress-test the plan against existing docs first (often via `/grill-with-docs`).

- **Read referenced docs completely.** When the user points you at files in `/tmp` or elsewhere that inform a feature, read them to EOF — do not report findings from a truncated read. A partial read of `refactor-storage-system.md` (stopped at line 500/625) was called out. If a file is truncated, re-read with offset until you hit the end.

- **Letter-labeled options in decision sessions.** When presenting multiple-choice options (especially during `/grill-with-docs`), label them A/B/C/D. The user prefers replying with a single letter rather than retyping the full answer. Do NOT bundle sub-questions — present one at a time even when they seem tightly coupled.

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

- **Fork:** `Seven74AI/music-library` — branch protection: `enforce_admins: true`, `required_reviews: 1`, `dismiss_stale_reviews: true`, required checks: `lint, typecheck, vitest, playwright-gate`, auto-merge ON
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

Same fork model as shop: workers push feature branches to fork → PR → auto-merge → reviewer (GitHub App) approves → squash merge.

## CI

Full CI: `lint` + `typecheck` + `vitest` + `playwright-gate` (consolidates 2 shards into one check)

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

- **Package manager divergence:** Fork = npm, upstream = pnpm
- **Reviewer self-approval:** GitHub App may show `authorAssociation: NONE` → admin-merge workaround (see `kanban-project-workflow`)
- **Empty git remote token:** The remote URL is `https://oauth2:TOKEN@github.com/...` but the token portion may be empty on a fresh clone. Pushing fails with "Authentication failed." Fix with `gh auth token | xargs -I{} git remote set-url origin "https://oauth2:{}@github.com/Seven74AI/music-library.git"`.
- **Circular dependency risk:** `service-playlist.server → track-batch-processor → playlist-utils → service-playlist` is a cycle if playlist-utils imports error classes from the facade. Keep `ServiceNotFoundError` / `NoTokensError` in `playlist-utils.server.ts` (where they're thrown), not in the facade.

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
4. Restore branch protection (reconstruct from known config — the GET response
   schema doesn't map to PUT):
   ```bash
   gh api -X PUT repos/Seven74AI/music-library/branches/main/protection \
     --input <(cat <<'EOF'
   {
     "required_status_checks": {"strict": true, "contexts": ["lint","typecheck","vitest","playwright-gate"]},
     "enforce_admins": false,
     "required_pull_request_reviews": {"dismiss_stale_reviews": true, "required_approving_review_count": 1},
     "restrictions": null,
     "allow_force_pushes": false,
     "allow_deletions": false
   }
   EOF
   )
   ```
5. Verify: `gh api repos/mnlamart/music-library/compare/main...Seven74AI:main --jq '.status'` → `identical`

## Domain Architecture

Audio archiving is being reimplemented (reversing ADR-004). Settled decisions (see `CONTEXT.md` for glossary):

- **Cookies**: Netscape-format cookies.txt at `/data/youtube-cookies.txt` for yt-dlp `--cookies`. Admin upload via panel. DB `YoutubeCookie` model for audit metadata only (uploadedBy, updatedAt, valid flag). Worker detects 3+ consecutive 403s → marks invalid → Telegram notification.
- **Rate limiting**: Same as ADR-003 — sleep intervals + long breaks every 6-8h (1-2h duration). Polling-based (admin-interruptible via 30s DB checks). User-agent rotation dropped.
- **ArchiveJob**: Separate model from TrackAudioFile. ArchiveJob tracks download lifecycle (pending/processing/completed/failed, retryCount, errorHistory, priority). TrackAudioFile stays purely a file record. "Can user download?" = `track.audioFiles.length > 0` regardless of origin (upload or archive).
- **Worker**: ADR-003 baseline — 2-min interval, max 2 concurrent downloads.
- **Storage paths**: Archive = `audio/{serviceName}/{trackId}.mp3` (deterministic). User upload = `audio/tracks/{trackId}/{service}/{format}/{timestamp}-{fileId}.{ext}` (existing ADR-010 convention). Keep separate.
- **Auto-enqueue**: New tracks created via import/playlist sync → create ArchiveJob with status='pending', priority=false. Worker picks up in FIFO order.
- **DB reset**: OK to wipe and rebuild schema — no backward-compat constraint on this feature.

When working on audio archiving, always consult `CONTEXT.md` first — it's the domain glossary. The condensed implementation reference is at `references/audio-archiving-implementation.md` (models, yt-dlp command, worker loop, retry strategy, file manifest). The original full docs are in `/tmp`: `audio-archive-feature.md` (plan), `003-audio-worker-architecture.md` (ADR-003), `refactor-storage-system.md` (storage layer).

## Kanban Task Skills (Matt Pocock flow)

This project uses the Matt Pocock skill flow (`/grill-with-docs` → `/to-prd` → `/to-issues` → `/implement`).

**Coder tasks** (via `hermes kanban create`):
```
--assignee coder \
--skill music-library \
--skill kanban-project-workflow \
--skill implement \
--skill tdd \
--skill code-review
```
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
- Fork synced to upstream (no divergence)
- Board clean
- Dependency bumps PR #37: cookie v2, eslint v10, vitest v4 applied with fixes
- **Audio archiving**: Reimplementing with cookie support. Architecture decisions in `CONTEXT.md` and issue [#38](https://github.com/Seven74AI/music-library/issues/38). Feature lives in `app/features/audio-archive/`. Key decisions: ArchiveJob separate from TrackAudioFile, yt-dlp cookies + sleep intervals, 2-min worker interval with polling breaks, direct presigned Tigris URLs for audio serving, Telegram Bot API for cookie-expiry notifications.