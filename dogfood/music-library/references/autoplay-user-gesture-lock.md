# Autoplay — Chromium "User Gesture Lock" (unlock on first gesture)

Verified against Chromium source `chromium/docs/media/autoplay.md` (the
authoritative doc, not the developer.chrome.com blog summary).

## Mechanism

Each `<audio>`/`<video>` element carries a **per-element "user gesture lock"**,
initialized `true` (blocked) when the element isn't allowed to autoplay. It is
unlocked (`false`) **only** by calling `play()` or `load()` on *that element*
synchronously inside a user gesture. The lock persists across `src` changes on
the same element and only re-locks when the element is recreated or moved to a
new document.

Implications that drive the design:

- Must hit the **same** element — no stub/primer element; the lock doesn't transfer.
- Must be **synchronous, inside the event handler** — not in a `useEffect` after
  async work.
- `load()` unlocks silently (no audible blip) and needs no `src`. A muted
  `play()`→`pause()` is a community refinement for silent unlocking, **not** a
  documented requirement — don't cite it as canonical.

## Why it matters in this app

`AudioPlayer` calls `play()` inside a `useEffect` (after async track/URL
resolution), so a *track tap* (not the play button) leaves the lock `true` and
the first autoplay is rejected. Only `togglePlayPause` (the play button) calls
`play()` directly in-gesture.

## Fix (two parts)

1. **Always mount `<audio>`** — extract into one `audioElement` const and return
   it in all three render branches (`!isVisible`, `!track`, normal) so
   `audioRef.current` exists before the first gesture. Safe because every
   `audioRef.current` read in the file is effect/handler-guarded (no render
   reads) — verify that before changing the mount condition.
2. **One-shot unlock** on first `pointerdown`/`keydown`:

```tsx
useEffect(() => {
  let unlocked = false;
  const unlock = () => {
    if (unlocked) return;
    unlocked = true;
    audioRef.current?.load();
    window.removeEventListener("pointerdown", unlock);
    window.removeEventListener("keydown", unlock);
  };
  window.addEventListener("pointerdown", unlock);
  window.addEventListener("keydown", unlock);
  return () => {
    window.removeEventListener("pointerdown", unlock);
    window.removeEventListener("keydown", unlock);
  };
}, []);
```

`pointerdown` fires before `click`, so the unlock lands before the track-tap's
`playTrack` runs.

## Pitfall

Do **not** use `{ once: true }` on each listener. That arms each event type
independently: after a `pointerdown` unlocks, the `keydown` listener stays armed,
and a later keypress calls `load()` — which **resets a playing element**. Use a
single shared `unlocked` flag and remove both listeners manually.

## Scope note

This fixes **first autoplay from a track tap**. It does NOT fix "next song
blocked while the screen is locked" — once the user has pressed play once the
lock is already cleared; the locked-screen block is the separate *hidden-page*
policy (`visibilitychange` recovery territory).
