# Cross-user unique-key clobbering bugs

A recurring data-isolation bug class in this repo. Learn the shape so it's caught in review,
not only after two users collide in prod.

## The bug class

A Prisma model has a **global** `@@unique(...)` that omits the owning user
(`userId`/`ownerId`), and an `upsert` keyed on that unique key **reassigns the owner in its
`update` branch**. When a second user acts on the same logical record, their upsert matches
the first user's row and silently steals/clobbers it.

Symptoms:
- Second user appears "not connected" / "not synced" even though their operation "succeeded"
  (their `findFirst({ providerName/serviceId, userId/ownerId })` finds nothing).
- First user's data is silently replaced with the second user's.

## Two instances found

1. **`Connection`** (YouTube OAuth callback) — `@@unique([providerName, providerId])` with
   `providerId` hardcoded to `"youtube"` for every user. Every YouTube connection collided on
   `("youtube","youtube")`. Fix: key on the real YouTube channel id
   (`createYouTubeService().getYouTubeUserInfo(tokens.access_token)` → `channels.list({ mine: true })`),
   and set `userId` in the `update` branch.
2. **`ServicePlaylist`** — `@@unique([serviceId, externalId])` global, upsert reassigning
   `ownerId`. Fix: `@@unique([serviceId, externalId, ownerId])` + `ownerId` in the upsert `where`.

## Diagnosis workflow

1. Grep `prisma/schema.prisma` for `@@unique` — flag any on a logically-per-user model that
   omits `userId`/`ownerId`.
2. Grep `app/**` for `.upsert(` and inspect: does the `where` include the owner? Does the
   `update` branch reassign `ownerId`/`userId`?
3. Intentionally-global models (do NOT "fix"): `Track.[serviceId, externalId]`, `Album`,
   `Artist`, `CoverImage`, `TrackAudioFile`, `ArchiveJob`, `DailyUsageStat`, `WorkerState`,
   `YoutubeCookie`, `Permission`, `Role`. `Track` being global is correct — per-user library
   membership lives in `UserTrack`, audio dedup in `TrackAudioFile`.

## Fix pattern

- Add the owner to the unique key and to the upsert `where` clause.
- SQLite migration (Prisma maps uniques to indexes): hand-write the SQL —
  `DROP INDEX "Model_a_b_key";` then
  `CREATE UNIQUE INDEX "Model_a_b_ownerId_key" ON "Model"("a","b","ownerId");`
  (`prisma migrate dev` is interactive — use `migrate deploy`). Naming: `{Model}_{cols}_key`
  for unique, `{Model}_{cols}_idx` for non-unique.

## Test pattern (integration, real DB — required)

A mocked-prisma unit test CANNOT catch a DB unique-constraint collision. Write an integration
test against the real per-pool test DB (`tests/setup/db-setup.ts` wires `DATABASE_URL` to a
copy of the migrated+seeded `tests/prisma/base.db`):

- `import { prisma } from "#app/utils/db.server"` — do NOT `vi.mock` db.server.
- `import { createUser } from "#tests/db-utils"` for unique users.
- Mock fns referenced inside `vi.mock` factories must be created via `vi.hoisted(() => ({ ... }))`
  — with static imports the factory runs before top-level `const`s init (TDZ error).
- Mock only the external boundary: `#app/utils/youtube.server` (`createYouTubeService`) and
  `#app/features/service-connection/service-connection.server` (`resolveServiceAccessToken`).
- For `ServicePlaylistService`, construct with `noopArchiveEnqueueAdapter` and mock
  `fetchPlaylistItems` → `[]` so `processBatches` stays trivial.
- Clean up in `beforeEach` via `deleteMany()` on the leaf tables then `user` (FK cascade covers
  connections).

The vitest `globalSetup` re-runs `prisma migrate deploy` + `prisma generate` when it sees a new
migration, so a new migration file is applied automatically — but run `npx prisma generate`
yourself before typecheck so the new compound `where` field exists in the generated client.

## Trap: skill docs describing unmerged features

`SKILL.md` + `references/public-playlist-sync.md` described the per-user `ServicePlaylist` key
and `syncServicePlaylistByUrl()` as if merged. They are NOT in upstream/main — they live on the
unmerged `feat/sync-playlist-by-url` branch (commit `206d61a`). Always verify schema/code against
the actual repo before trusting the skill's "current state" claims.

## Migration-conflict risk with the unmerged branch

PR #162's `20260826120000_per_user_service_playlist_unique` drops
`ServicePlaylist_serviceId_externalId_key`. The unmerged `feat/sync-playlist-by-url` branch carries
`20260815120000_add_sync_source_and_per_user_playlist_unique`, which performs the same `DROP INDEX`
(plus adds a `syncSource` column). If that branch ever merges, its migration will fail on the
now-missing index — reconcile it against PR #162's migration before merging.
