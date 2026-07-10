# Stale `audioSrc` Race Condition — Diagnosis

**Date:** 2026-07-09 (diagnosis), 2026-07-09 (proper fix)
**PRs:** #89 (initial `setAudioSrc(undefined)` fix — insufficient), #90 (proper `urlReadyRef` fix)
**File:** `app/components/audio-player.tsx`

## Symptoms

- Next button: clicking does nothing, player stays on current track
- Auto-advance: when track ends (`ended` event), next track does not play
- Track #1 always plays correctly; only subsequent tracks are affected
- No console errors, no network failures — completely silent

## Root Cause — React Effect Ordering Race

The `audioSrc` fetch effect (line 58) and the play effect (line 92) share `track?.id` as a dependency, so they fire in the same render cycle. **React runs effects in declaration order, but `setState()` calls are queued — not applied immediately.** The play effect sees the PREVIOUS track's stale `audioSrc`.

### Race condition trace

Starting state: track A playing, `audioSrc = urlA`, `previousTrackIdRef = "trackA"`

| Step | Event | `audioSrc` | Effect action |
|------|-------|-----------|---------------|
| 1 | `setCurrentTrack(trackB)` | `urlA` (stale!) | Effect 1 runs: `setAudioSrc(undefined)` QUEUED, fetch starts |
| 2 | Same render cycle | `urlA` (still stale!) | Effect 2 runs: `trackB && urlA && "trackB" !== "trackA"` → **all true** |
| 3 | `previousTrackIdRef = "trackB"` | — | Guard burned prematurely |
| 4 | `audioRef.play()` on `<audio src={urlA}>` | — | Plays stale audio (or does nothing) |
| 5 | React flushes batch | `undefined` | Effect 2 fires: `audioSrc` falsy → skipped |
| 6 | Fetch completes → `setAudioSrc(urlB)` | `urlB` | Effect 2 fires: `"trackB" !== "trackB"` → **FALSE → skip** |

### Why `setAudioSrc(undefined)` didn't fix it (PR #89)

The one-liner added in PR #89 (`setAudioSrc(undefined)` at the top of the fetch effect) was insufficient because React runs effects synchronously in declaration order BEFORE flushing queued state updates. Effect 2 runs in the same render cycle as Effect 1, with the old `audioSrc` value. The `undefined` only arrives on the NEXT render, by which time Effect 2 has already consumed `previousTrackIdRef`.

### Why track #1 works

Before any track plays: `audioSrc = undefined` (falsy). No stale URL to trigger the guard.

## Proper Fix — `urlReadyRef` (PR #90)

Replace `previousTrackIdRef` with a directional ref that gates the play effect:

```typescript
const urlReadyRef = useRef(false)

// Effect 1: fetch URL
useEffect(() => {
    if (!audioRouteUrl || !track) {
        setAudioSrc(undefined)
        return
    }
    
    setAudioSrc(undefined)
    urlReadyRef.current = false   // gates Effect 2 immediately
    
    let cancelled = false
    fetch(audioRouteUrl)
        .then(res => res.json())
        .then(data => {
            if (!cancelled) {
                urlReadyRef.current = true   // only now allow play
                setAudioSrc(data.url)
            }
        })
        .catch(err => {
            console.error('Failed to fetch audio URL:', err)
            if (!cancelled) setAudioSrc(undefined)
        })
    
    return () => { cancelled = true }
}, [audioRouteUrl, track?.id])

// Effect 2: play when ready
useEffect(() => {
    if (audioRef.current && track && audioSrc && urlReadyRef.current) {
        urlReadyRef.current = false   // consume
        setIsPlaying(false)
        audioRef.current.volume = volume
        if (!isManualPlayRef.current) {
            audioRef.current.play()
                .then(() => setIsPlaying(true))
                .catch(() => setIsPlaying(false))
        }
        isManualPlayRef.current = false
    }
}, [track?.id, audioSrc, volume, loopMode])
```

**How it works:**
- Same render cycle: `urlReadyRef` is `false` (set in Effect 1 before fetch) → Effect 2 skips
- `setAudioSrc(undefined)` flush: `audioSrc` is falsy → Effect 2 skips
- Fetch completes: `urlReadyRef` set to `true`, `audioSrc` set to `urlB` → Effect 2 fires

## General Pattern

This is a general React gotcha: `setState()` in one effect does not prevent a sibling effect from seeing the old value in the same render. The fix pattern is a directional ref (`false` → `true`) where the consumer only gates on `true`. See `diagnose` skill `references/react-effect-ordering-race.md` for the generalized pattern.
