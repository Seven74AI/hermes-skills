# Queue navigation & playback primitives

For implementing queue click-to-play (ADR-018) and the artist full-discography queue (ADR-022), and
for understanding how `playTrack` builds a queue vs. how to jump *within* an existing one.

## The navigation state machine

`QueueNavigationState = { upNext, spine, spineOrder, spinePosition, loopMode }`
(`app/features/queue/queue-navigation.ts`). **`spinePosition` is an index into `spineOrder` (the
play order), NOT the raw spine index.**

Pure helpers (all in `queue-navigation.ts`):
- `getSpinePlayOrder(state)` = `spineOrder.slice(spinePosition).map(i => spine[i])`.
- `getUpcomingSpinePlayOrder(state)` = `spineOrder.slice(spinePosition + 1)` (excludes now-playing).
- `getQueueSpineDisplayTracks(state, hasCurrentTrack)` — what the sheet shows in the spine section.
- `getTrackAtTarget(state, { zone, index })` — resolve a track from a `QueueTarget`; for spine,
  `index` is a **play-order** index (`spine[spineOrder[index]]`).
- `advanceAfterPlay(state, played)` — upNext: drop the played index; spine: `spinePosition = played.index`.
- `resolveNextTrack` / `resolvePreviousTrack` — upNext takes priority over loop-one; loop-one returns
  the current `spinePosition`.
- `findSpinePositionForTrackId(state, trackId)` — play-order position resolved by **id**.
- `buildFlatQueueView(state)` = `[...upNext, ...getSpinePlayOrder(state)]`.
- `flatIndexForSpinePosition(state, pos)` = `upNext.length + max(0, pos - spinePosition)`.
- `QueueTarget = { zone: "upNext" | "spine"; index: number }`.

## Position resolution in `startSpinePlayback`

`startSpinePlayback(track, context, explicitIndex?)` (`audio-player-provider.tsx`):
1. load spine via `loadSpineForContext` → `fetchQueueSpine`.
2. `order = buildShuffledOrder(spine.length)`.
3. `resolvedPosition`:
   - if `explicitIndex !== undefined && spine[explicitIndex]?.id === track.id` → `order.findIndex(i => i === explicitIndex)`;
   - else `findSpinePositionForTrackId(...) ?? 0`.
4. set spine / spineOrder / spinePosition, hydrate, play.

`explicitIndex` (the row index passed when `usePlaybackIndex` is true) only works when the rendered
list is a *prefix of the spine in the same order*. For infinite-scroll / partial lists set
`usePlaybackIndex={false}` so clicks resolve by id via `findSpinePositionForTrackId` — the search
page already does this (`search-results.tsx`).

## `playResolvedTrack` is the internal "play this queue track" primitive

`playResolvedTrack(queueTrack)` = `hydrateAround(id)` → resolve full track → `setCurrentTrack`.
This is what a click-to-play jump calls — **not** `playTrack`, which rebuilds the queue from a fresh
context (and resets state when the context differs).

## `removeTrackFromPlaylist` index semantics

`removeTrackFromPlaylist({ zone, index })`:
- upNext: `index` is the raw upNext index; also decrements `upNextPlayNextCount` if `index < count`.
- spine: `index` is a **play-order** index (`spineOrder[index]` = raw spine index). Removing before
  `spinePosition` decrements it; removing at `spinePosition` advances (`advanceAfterPlay` + `playResolvedTrack`).

## QueueSheet display → play-order mapping

`QueueSheet` (`audio-player.tsx`) renders three zones: Now playing (`currentTrack`), Up Next, spine.
Spine rows come from `getQueueSpineDisplayTracks` (play-order `spinePosition+1 … end`), so a display
row `d` maps to play-order index `spinePosition + 1 + d` — exactly what `removeSpineTrack` already
does (`removeTrackFromPlaylist({ zone: "spine", index: spinePosition + 1 + displayIndex })`). A
click-to-play handler must apply the same mapping.

## `playQueueTrack` seam (ADR-018)

One new provider fn `playQueueTrack(target: QueueTarget)`:
- `queueTrack = getTrackAtTarget(navigationState, target)`; if null, return.
- spine → `setSpinePosition(target.index)`; upNext → `setUpNext(prev => prev.slice(target.index + 1))`
  and decrement `upNextPlayNextCount` by the number of discarded "play next" items (indices `< target.index`).
- `playResolvedTrack(queueTrack)`.

Loop mode is left untouched — `loop="one"` reads `spinePosition`, and upNext already takes priority
over loop-one in `resolveNextTrack`.
