# Player state & queue architecture

Foundation for any cross-device queue persistence / "resume where I left off" work.

## Player state is 100% in-memory

`app/components/audio-player-provider.tsx` holds everything in React state:
`currentTrack`, `isPlayerVisible`, `upNext`, `spine`, `spineTotal`, `spineOrder`,
`spinePosition`, `playContext`, `loopMode`, `isShuffleEnabled`, `isLoadingNext`.

Track *content* lives in `PlaybackHydrationCache` (an in-memory `Map<trackId, FullTrack>`,
`app/features/queue/queue-hydration.ts`), hydrated lazily in batches.

**Nothing survives a reload or a second browser.** `localStorage` is only used for:
- volume (`app/utils/player-preferences.ts`, key `music-library:player-volume`)
- autoplay-guide dismissed / failure count (`use-autoplay-guide.ts`)
- recent searches (`routes/search.tsx`)
- offline playlist metadata (`offline-playlist-metadata.client.ts`)
- offline root shell (`offline-root-shell.client.ts`)
Never the queue.

## Queue model: spine + order + position + upNext

The queue is *derived* from a **spine** (the source track list) plus three overlays:

- **spine** — `QueueTrack[]` (`{ id, title, artist }`), fetched fresh via
  `fetchQueueSpine(context)` → `/api/queue-spine?...` (`app/features/queue/queue-spine.ts`).
- **spineOrder** — a permutation of indices into the spine (the shuffle / play order).
- **spinePosition** — index into the *play order* (not the spine).
- **upNext** — ad-hoc `QueueTrack[]` from "play next" (the only non-derivable queue content).
- **loopMode** (`off`/`all`/`one`), **isShuffleEnabled**, **playContext**.

`LoopMode` has a single source of truth: `export const LOOP_MODES = ["off","all","one"] as const`
+ `export type LoopMode = (typeof LOOP_MODES)[number]` in `queue-navigation.ts`. Anything that
validates `loopMode` at runtime (e.g. `player-state-cache.client.ts`) must import `LOOP_MODES`
rather than re-declaring the union — the drift risk is real, the union is otherwise spelled out in
three places (`queue-navigation.ts`, `audio-player-provider.tsx`, `player-state-cache.client.ts`).

`playContext` types: `library`, `playlist`, `artist`, `album`, `track`, `music`.

## Spine is deterministic per context

`app/features/queue/queue-spine.server.ts` — `fetchQueueSpine(userId, params)`:
- **library** — `UserTrack` ordered `createdAt desc` (hasAudioOnly).
- **playlist** — `UserPlaylistTrack` ordered `position asc`.
- **artist** — `Track` `createdAt desc`, `take: 50`.
- **album** — `Track` `createdAt asc`.
- **track** — single track.

So the spine can be re-derived from the context. Reordering hazard: library is
`createdAt desc`, so *any* added track shifts every index.

## Shuffle is seeded (PR #245) — permutation still index-based

`app/features/queue/queue-shuffle.ts` — `createSeededRandom(seed)` (mulberry32) +
`generateShuffleSeed()`. `createShuffledOrder(length, isShuffleEnabled, seed)` returns
`[0..length)` when shuffle is off, else Fisher-Yates over the seeded PRNG. A 32-bit
`shuffleSeed` (not the permutation) is what gets persisted to `PlayerState` — same seed +
same length reproduces the identical order. `reshuffleFromCurrent(order, position)` preserves
the prefix and re-shuffles the suffix. The permutation is an index array — a seed is
*positional*, so it degrades (deterministic but different) if the spine length changes
between save and restore; accepted tradeoff for a 15k-track library (imperceptible).

## Hydration

`PlaybackHydrationCache.hydrateMissing(ids)` → `fetchPlaybackBatch(ids)` →
`GET /api/tracks/playback?ids=a,b,c`. `PLAYBACK_BATCH_MAX_IDS = 200`
(`app/features/queue/constants.ts`). Track access is scoped per-user in
`fetchPlaybackTracks` (`app/features/queue/queue-playback.server.ts`).

## Useful existing helpers for restore

- `findSpinePositionForTrackId(state, trackId)` (`queue-navigation.ts`) — locate the
  current track's position in the play order by **id** (robust anchor vs a raw index).
- `toQueueSpineContext(context)` in `audio-player-provider.tsx` — maps `playContext`
  → spine context.
