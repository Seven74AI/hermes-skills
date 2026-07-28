# Autoplay Guide

## Problem

Browsers block `audioElement.play()` when there's no prior user gesture. This is
by design — the Autoplay Policy prevents sites from auto-playing audible media
without user interaction.

When the player's autoplay is blocked, the user sees a toast but has no path to
permanently fix it. They keep hitting the same error.

## Solution

Three-part approach:

### 1. Detect proactively — `navigator.getAutoplayPolicy()` (Chrome/Edge)

```typescript
// Chrome 100+, Edge 100+
if ("getAutoplayPolicy" in navigator) {
  const policy = (
    navigator as Navigator & {
      getAutoplayPolicy: (type: string) => "allowed" | "allowed-muted" | "disallowed";
    }
  ).getAutoplayPolicy("mediaelement");
  // "allowed" | "allowed-muted" | "disallowed"
}
```

Returns `"disallowed"` when Chrome has never seen the user play media on this
site. Other browsers (Safari, Firefox) don't expose this API, so we fall back to
the failure counter.

### 2. Track failures — localStorage counter

Every time the existing `play()` promise rejects (the catch at `audio-player.tsx`
line 912), call `recordAutoplayFailure()`. This increments a counter in
localStorage.

```typescript
// In audio-player.tsx, inside the play() catch:
playPromise.catch(() => {
  setIsPlaying(false);
  setPlaybackError("Autoplay was prevented by your browser. Press play to start.");
  recordAutoplayFailure(); // NEW — tracks count
  toast({ ... });
});
```

### 3. One-time guide dialog

`useAutoplayGuide()` hook in `app/hooks/use-autoplay-guide.ts` checks on mount:
- `getAutoplayPolicy("mediaelement") === "disallowed"` → show immediately
- `localStorage.autoplay-failures >= 2` → show after repeated failures

The `AutoplayGuideDialog` component shows browser-specific instructions. Once
dismissed (localStorage flag), it never shows again.

## Browser-Specific Instructions

- **Chrome/Edge**: Click the lock/tune icon in the address bar → Site Settings → Sound → Allow
- **Safari**: Right-click the address bar → Settings for This Website → Auto-Play → Allow All Auto-Play
- **Firefox**: Click the autoplay icon in the address bar → Allow Audio and Video

## Files

- `app/hooks/use-autoplay-guide.ts` — hook, `recordAutoplayFailure()`, `dismissAutoplayGuide()`
- `app/components/autoplay-guide-dialog.tsx` — dialog with browser-specific instructions
- `app/components/audio-player.tsx` — calls `recordAutoplayFailure()` in catch block
- `app/root.tsx` — renders `<AutoplayGuideDialog />` in `<App />`

## Testing

The dialog only fires in browsers without autoplay permission. In development:
- Chrome: open an incognito window (resets MEI)
- Safari: never granted autoplay to localhost
- Or: manually set `localStorage.autoplay-failures = "2"` to force the dialog
