# React Effect Ordering Race — Stale State in Sibling Effects

## The Bug

You have two `useEffect` hooks in declaration order:

1. **Effect A** — calls `setState(undefined)` to reset stale data, then starts an async fetch
2. **Effect B** — reads `state` and acts on it (e.g., plays audio, starts animation)

Both share a dependency (`trackId`, `userId`, etc.) so they fire in the same render cycle.

**React runs effects in declaration order — but state updates are queued, not applied immediately.** Effect B sees the OLD value of `state`, not the `undefined` queued by Effect A.

```tsx
// ❌ BROKEN — Effect B sees stale audioSrc
useEffect(() => {
  setAudioSrc(undefined)  // QUEUED, not flushed
  fetch(url).then(data => setAudioSrc(data.url))
}, [trackId])

useEffect(() => {
  // audioSrc is STILL the previous track's URL here
  if (audioSrc && trackId !== previousRef.current) {
    previousRef.current = trackId
    play()  // plays PREVIOUS track, then burns previousRef
  }
}, [trackId, audioSrc])
```

## The Consequence

Effect B fires with stale state → consumes a one-shot guard (sets `previousRef`) → when the real state arrives later, the guard says "already handled" → the correct behavior **never fires**.

## The Fix — Ref-Based Ready Gate

Replace the stale-state-sensitive guard with a ref that is:
- **`false`** during the same render cycle (set in Effect A before the async work)
- **`true`** only when the async work completes and the new state is committed

```tsx
// ✅ CORRECT — urlReadyRef gates the play effect
const urlReadyRef = useRef(false)

useEffect(() => {
  setAudioSrc(undefined)
  urlReadyRef.current = false   // gates Effect B immediately
  fetch(url).then(data => {
    urlReadyRef.current = true  // only now is Effect B allowed
    setAudioSrc(data.url)
  })
}, [trackId])

useEffect(() => {
  // Skipped in same render (urlReadyRef is false)
  // Skipped on setAudioSrc(undefined) flush (audioSrc is falsy)
  // Fires ONLY when urlReadyRef is true AND audioSrc is the new URL
  if (audioSrc && urlReadyRef.current) {
    urlReadyRef.current = false  // consume
    play()
  }
}, [trackId, audioSrc])
```

## Why Not Just Use a Ref for the Guard Value?

`previousTrackIdRef` (`useRef`) synchronously updates the ref value — so it would
also be consumed in the same render cycle by Effect B. The fix is a **directional**
ref: it goes `false → true` but Effect B only gates on `true`. The `false` state
is the default; it's the `true` state that's the event signal.

## Diagnosis Checklist

When a React effect-based behavior fires once and then never again on subsequent state changes:

1. Count the effects that share a dependency. Are they in the right order?
2. Does one effect `setState(...)` while another reads that same state?
3. If a ref is used as a guard, is it consumed by the stale render before the fresh state arrives?
4. Trace the render cycle: declaration order → queued state → flushed → fetch resolve → new state

## Real Case

music-library `AudioPlayer`: `setAudioSrc(undefined)` in the URL-fetch effect didn't
prevent the play effect from firing with the previous track's presigned URL. The play
effect burned `previousTrackIdRef` on the stale render; when the new URL resolved,
`previousTrackIdRef` already matched the new track ID → never played. Fixed by
replacing `previousTrackIdRef` with `urlReadyRef` (see `fix/player-next-auto-advance`).
