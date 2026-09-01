# Autoplay Next Track — auto-advance blocking on lock screen

## Code path (next-track auto-advance)

`ended` event → `handleEnded` (`app/components/audio-player.tsx`) →
`onNext()` → `playNext()` → `advanceToTarget()` → `playResolvedTrack()`
(`app/components/audio-player-provider.tsx`). `playResolvedTrack` is async and
`await hydrateAround(queueTrack.id)` before `beginPlayback()` +
`setCurrentTrack(next)`. `beginPlayback()` sets `wantsAutoPlayRef.current = true`
and bumps `playbackToken`.

The actual `audioRef.current.play()` fires in a `useEffect` in `audio-player.tsx`
(keyed on `track?.id, audioSrc, playbackToken, volume, isMuted`), gated by
`loadedTrackIdRef.current === track.id` and
`playbackToken !== previousPlaybackTokenRef.current`.

## Diagnosis — distinguish two distinct failure modes

The symptom tells you the cause:

1. **"Autoplay blocked" toast, no title/timer update** → `play()` rejected with
   `NotAllowedError` (permission). This is the *first-play-from-tap* case; the
   per-element "user gesture lock" is still set. See
   `references/autoplay-user-gesture-lock.md`.
2. **"Title + timer update, but no sound until unlock"** → `play()` *succeeded*
   (`timeupdate` fires, `currentTime` advances). This is **not** permission
   rejection — it's Android dropping background audio during the transition.

The "no sound until unlock" case is caused by two gaps:

- **The next track's presigned URL is fetched at transition time.**
  `resolveTrackPlaybackSource` → `fetch('/resources/audio/:id')` runs *after*
  `ended`, on a hidden/throttled page. This network round-trip is the dominant gap.
- **`handleEnded` reset the playing state mid-transition.** `setIsPlaying(false)`
  flipped `navigator.mediaSession.playbackState` to `"paused"` at the exact
  moment audio should continue, releasing audio focus.

## Fix (implemented)

- **Prefetch the next track's presigned URL** while the current one plays —
  `prefetchPlaybackAudioUrl` (deduped + cached in
  `resolve-playback-url.client.ts`), triggered from the provider whenever the
  current track / queue changes. The transition is then off the network.
- **Keep `isPlaying`/mediaSession "playing" through auto-advance.** `handleEnded`
  only stops at end of queue; the play effect only clears the playing flag when
  NOT auto-advancing.

## Remaining lever (unverified)

If the locked-screen stall still reproduces, preload the audio *data* itself via
a second `<audio>` element (preload the next track's bytes, not just its URL).

## Supporting infra (unchanged)

- `app/hooks/use-autoplay-guide.ts` — `getAutoplayPolicy()` detection, failure
  counter (`recordAutoplayFailure()`), guide dialog state.
- `app/components/autoplay-guide-dialog.tsx` — browser-specific instructions.
- Full Media Session action handlers in `audio-player.tsx`.
- `app/utils/media-session.client.ts` — metadata + position state helpers.
