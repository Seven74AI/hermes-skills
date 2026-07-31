# Offline Audio Playback — Seamless Network → Cache Transition

When the HTML5 `<audio>` element is playing from a remote URL (Tigris presigned) and
the app goes offline, the browser's internal buffer eventually depletes and the element
fires `MEDIA_ERR_NETWORK`.  To resume playback from the offline cache without
interruption, use a two-layer defense.

## Architecture

```
resolveTrackPlaybackSource(trackId)
  └─ resolvePlaybackAudioUrl(trackId)     // check OPFS blob → blob: URL
     └─ fetchRemotePlaybackAudioUrl(trackId)  // fetch /resources/audio/:id → Tigris URL
```

The resolution is **offline-first**: if a cached blob exists, it wins.  The remote fetch
only runs as a fallback.  On initial load when online, the blob check returns null and
the remote URL is used.

## Two-Layer Defense for Seamless Transition

### Layer 1: Proactive — `online`→`offline` useEffect

When the browser fires the `offline` event while a track is playing:

1. Detect the transition: `prevOnlineRef` tracks the previous `isOnline` value
2. If `wasOnline && !isOnline` and a track is playing:
   - Call `resolvePlaybackAudioUrl(track.id)` to get the cached blob URL
   - If found: save `audio.currentTime` and `.paused` state
   - Set `audio.src = blobUrl`, restore `currentTime`, call `play()` if was playing
   - Update `audioSrc` state so React stays in sync
3. If no cached blob: do nothing — let Layer 2 handle it

### Layer 2: Reactive — `handleError` on MEDIA_ERR_NETWORK

If the browser's buffer drains before Layer 1 completes (or Layer 1 finds no blob):

1. Check `error.code === 2` (MEDIA_ERR_NETWORK)
2. If a track is loaded:
   - Save `currentTime` and pause state
   - Call `resolvePlaybackAudioUrl(track.id)`
   - If blob found: swap src, restore position, resume play
   - If no blob: fall through to `setPlaybackError` + `setAudioSrc(undefined)`
3. On success: clear `playbackError`, set new `audioSrc`

## Key Files

| File | Role |
|------|------|
| `app/components/audio-player.tsx` | `<AudioPlayer>` component — `<audio>` element + event handlers |
| `app/components/audio-player-provider.tsx` | Queue/playback state management |
| `app/features/offline-storage/resolve-playback-url.client.ts` | `resolveTrackPlaybackSource`, `resolvePlaybackAudioUrl`, blob URL cache |
| `app/features/offline-storage/offline-storage.client.ts` | OPFS-backed `OfflineStorage` — `resolvePlaybackBlob`, `downloadTrack` |
| `app/hooks/use-online-status.ts` | `useOnlineStatus()` — reacts to `window` online/offline events |

## Testing: MediaError in jsdom

jsdom does not expose the `MediaError` constructor, so use numeric constants in
tests and in the code that tests must cover:

| Constant | Value |
|----------|-------|
| `MEDIA_ERR_ABORTED` | 1 |
| `MEDIA_ERR_NETWORK` | 2 |
| `MEDIA_ERR_DECODE` | 3 |
| `MEDIA_ERR_SRC_NOT_SUPPORTED` | 4 |

When adding `error` event handling that branches on error code, use the numeric
value directly (`errorCode === 2`) instead of `MediaError.MEDIA_ERR_NETWORK`.

Mock the `resolvePlaybackAudioUrl` export in audio-player tests — it's called by
both the proactive useEffect and the reactive handleError, so the module mock in
`app/components/audio-player.test.tsx` must include it.

## Race Between Layers

Both Layer 1 (proactive swap) and Layer 2 (handleError) call `resolvePlaybackAudioUrl`.
Whichever resolves first sets `src` to the blob URL. The second resolution:

- Sets `src = blobUrl` again — no-op (same value for the HTMLMediaElement)
- Sets `currentTime` to a value captured ~0.1–0.2s earlier (imperceptible gap)
- Calls `play()` on an already-playing element — no-op

## Direct DOM Swap + React State Sync

When doing `audioRef.current.src = blobUrl` directly (outside React's render cycle),
always follow with `setAudioSrc(blobUrl)` so React's reconciler sees the matching value
on the next render. This prevents React from resetting the `src` attribute and
disrupting playback. The `playbackToken` guard in the playback effect prevents
`currentTime` from being reset to 0 on this state update.

## Source-Resolution useEffect: Do Not Depend on isOnline

`resolveTrackPlaybackSource` is already offline-first — it checks the blob URL before
trying the remote fetch.  Adding `isOnline` to the dependency array of the
source-resolution useEffect causes it to re-run on every online/offline transition,
which calls `setAudioSrc(undefined)` and kills the currently-playing audio.

The source-resolution useEffect's dependencies should be `[audioFile, track?.id]` only.
Online/offline transitions are handled by the separate proactive swap useEffect.
