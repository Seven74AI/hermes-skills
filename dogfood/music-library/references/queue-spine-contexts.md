# Queue Spine Contexts — playback context → spine fetch

How a "play context" becomes the queue's **spine** (the tail of the queue after
Now playing + Up Next). Complementary to `player-state-queue-architecture.md`
(which covers the in-memory spine/order/position model and hydration batches).

## Playback context types

`PlaylistContext` (client, `audio-player-provider.tsx`):
`library | playlist | artist | album | track | music`.

- `music` has **no spine** — `toQueueSpineContext()` and `playContextToJson()`
  both return `null` for it (falls through to `fetchOfflineTracks`).
- Every other type maps 1:1 to a `QueueSpineContext` via `toQueueSpineContext()`:
  - `library` → `{ type: "library" }`
  - `playlist` + `playlistId` → `{ type: "playlist", playlistId }`
  - `artist` + `artistId` → `{ type: "artist", artistId }`
  - `album` + `albumId` → `{ type: "album", albumId }`
  - `track` + `trackId` → `{ type: "track", trackId }`

## Server fetch — `fetchQueueSpine` (`app/features/queue/queue-spine.server.ts`)

`QUEUE_TRACK_SELECT` = `{ id, title, artist: { id, name } }` — minimal on purpose;
full tracks are hydrated client-side via `PlaybackHydrationCache`.

Per-context query semantics:

| context  | query                                             | orderBy          | note |
|----------|---------------------------------------------------|------------------|------|
| library  | `userTrack` (hasAudio via `buildLibraryUserTracksWhere`) | `createdAt desc` | full list |
| playlist | `userPlaylistTrack` (owner-scoped)                | `position asc`   | full list |
| artist   | `track.where({ artistId })`                       | `createdAt desc` | **`take: 50` hardcoded — the ONLY capped context** |
| album    | `track.where({ albumId })`                        | `createdAt asc`  | full list |
| track    | `track.findUnique({ id })`                        | —                | single |

Client URL builder (`app/features/queue/queue-spine.ts`) fetches with
`redirect: "manual"` and treats any 3xx as `AuthExpiredError` → redirect `/login`.

## Play flow

`playTrack(track, context, index?)` →
  `startSpinePlayback(track, context, index)`:
  1. `loadSpineForContext(context)` → `toQueueSpineContext` → `fetchQueueSpine`
     (falls back to `fetchOfflineTracks` when `spineContext` is null or the fetch
     fails/errors).
  2. `buildShuffledOrder(len)` honours the current `shuffleSeed`.
  3. Resolve `spinePosition`: use `explicitIndex` iff
     `loadedSpine.tracks[explicitIndex]?.id === track.id`, else
     `findSpinePositionForTrackId(...) ?? 0`.

## Queue sheet zones (`audio-player.tsx` `QueueSheet`)

Three zones, rendered in order:
1. **Now playing** — `currentTrack` (single row, `isCurrentlyPlaying`).
2. **Up Next** — `upNext` array.
3. **Spine** — `spine` (rest of queue; virtualized past `SPINE_VIRTUAL_THRESHOLD`).

`QueueTrackItem` exposes only a remove action — **no click-to-play**. The provider
API surface (`AudioPlayerContextType`) has `playTrack`, `playNextTrack`, `addToUpNext`,
`addToQueue`, `removeTrackFromPlaylist`, `removeCurrentFromQueue`,
`hydrateTracksForDisplay` — but **no "jump to this queue position" function**. Jumping
to an arbitrary spine/upNext index needs a new provider function that mutates
`spinePosition` (spine) or drops upNext entries (upNext), then calls
`playResolvedTrack(queueTrack)`.
