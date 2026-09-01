# Public Playlist Sync (by URL)

> ⚠️ **UNMERGED.** This feature lives on `feat/sync-playlist-by-url` (commit `206d61a`),
> NOT upstream/main. `syncServicePlaylistByUrl()`, the `syncSource` column, and its
> per-user unique migration are absent from main. The per-user `ServicePlaylist` key
> was landed separately in PR #162. See `references/cross-user-unique-key-bugs.md`.

Sync a YouTube playlist the user does **not** own, by pasting a playlist URL.
No OAuth connection required — fetches with the `YOUTUBE_API_KEY`.

## Why it's a separate path

The existing OAuth sync (`syncServicePlaylist`) requires `resolveServiceAccessToken`
and every fetch builds an `oauth2Client`. Public playlists don't need OAuth — the API
key already works for `playlists.list` / `playlistItems.list` / `videos.list` on
public/unlisted data (the single-track import page already uses it).

## Schema

- `ServicePlaylist` unique key: **`[serviceId, externalId, ownerId]`** (per-user). Was
  `[serviceId, externalId]` — globally unique, so two users syncing the same public
  playlist collided. Migration `20260815120000_add_sync_source_and_per_user_playlist_unique`.
- `ServicePlaylist.syncSource` (String, default `"connected"`): `"connected"` = OAuth
  (own playlists), `"url"` = API-key (public). Drives re-sync routing.

The codebase uses plain `String` columns, **not** Prisma enums, for status-like fields
— follow that convention (no `enum SyncSource`).

## Key files

- `app/utils/youtube-playlist-url.ts` — `extractYouTubePlaylistId()`: reads the `list`
  query param from `youtube.com/playlist`, `music.youtube.com`, `watch?v=…&list=…`;
  accepts raw `PL…`/`OLAK5uy_…`/`RD…`/`UU…` IDs. Playlist IDs are NOT fixed-length.
- `app/utils/youtube.server.ts` — `getPublicPlaylist` / `getPublicPlaylistItems` /
  `checkVideosExistPublic` (API-key; mirror the OAuth methods via `this.youtube`, plus a
  shared `classifyApiError` helper).
- `app/features/service-playlist/youtube-playlist-provider.server.ts` — `fetchPublicPlaylist`
  / `fetchPublicPlaylistItems` / `resolvePublicVideoExistence` (concrete class methods).
- `app/features/service-playlist/playlist-sync-provider.server.ts` — interface gained
  **optional** `fetchPublicPlaylist?` / `fetchPublicPlaylistItems?` / `resolvePublicVideoExistence?`
  seams (keeps the service decoupled from the concrete provider).
- `app/features/service-playlist/service-playlist.server.ts` — `syncServicePlaylistByUrl()`,
  `buildOAuthAuth()`, `buildPublicAuth()`.
- `app/routes/music+/services+/youtube+/index.tsx` — "Sync a Playlist by URL" card
  (always visible), action intent `sync-by-url`, navigates to the playlist detail page
  when `pendingMatches` are returned.

## Auth-context pattern

`registerAndSyncPlaylist` / `resyncExistingPlaylist` were refactored to take a `SyncAuth`
context instead of resolving OAuth internally:

```ts
type SyncAuth = {
  accessToken: string;                                        // sentinel for lookupVideoExistence
  resolveVideoExistence?: PlaylistSyncProvider["resolveVideoExistence"];
  fetchPlaylist: (externalId) => Promise<YouTubePlaylist>;    // required for register only
  fetchPlaylistItems: (externalId) => Promise<YouTubePlaylistItem[]>;
};
```

- `buildOAuthAuth()` → resolves OAuth token, binds `syncProvider.fetchPlaylist(id, token)` etc.
- `buildPublicAuth()` → binds `syncProvider.fetchPublicPlaylist(id)` etc.; `accessToken` is
  `process.env.YOUTUBE_API_KEY ?? "public"` (non-empty so `lookupVideoExistence` probes
  rather than short-circuiting to "no-probe").

`syncServicePlaylist` (OAuth entry) still resolves OAuth for the register path, but on an
existing playlist it branches on `existingPlaylist.syncSource === "url"` → public re-sync.

## Pitfalls

- **Call provider methods through the object, not a bare reference.** Extracting
  `const fetchPlaylist = syncProvider.fetchPublicPlaylist` and calling `fetchPlaylist(x)`
  later loses `this` (`Cannot read properties of undefined (reading 'youtubeService')`).
  Use `syncProvider.fetchPublicPlaylist!(x)` inside the closure (or `.bind(syncProvider)`).
- **`prisma migrate dev` is interactive** — for an additive schema change, hand-write the
  migration SQL matching Prisma's index naming (`{Model}_{cols}_key` = unique,
  `{Model}_{cols}_idx` = non-unique), then `npx prisma migrate deploy && npx prisma generate`.
- **Track still uses `[serviceId, externalId]`** — don't confuse it with the new
  per-user ServicePlaylist key when grepping `serviceId_externalId`.

## Tests

- `app/utils/youtube-playlist-url.test.ts`
- `app/utils/youtube-public.test.ts` (mocks `googleapis` — `this.youtube` = API-key client)
- `app/features/service-playlist/service-playlist-by-url.server.test.ts` (needs
  `servicePlaylist.upsert` in the prisma mock, plus public methods on the `createYouTubeService` mock)
