# Mobile Layout Architecture

## Z-Index Hierarchy (bottom to top)

```
Player mini-bar:    fixed bottom-16  z-50
Bottom nav:         fixed bottom-0   z-[51]  (above sheet backdrops)
Sheet overlay:      fixed inset-0    z-50
Sheet content:      fixed            z-50
Search page:        fixed inset-0    z-[80]  (full-screen, covers everything)
Toast:              fixed            z-[100]
```

Bottom nav sits **above** sheet backdrops (z-51 > z-50) intentionally — the sheet's
`shadow-lg` would visually cut into the nav bar if the overlay sat above it.

## `--bottom-bar-height` CSS Custom Property

The bottom chrome on mobile is variable:
- **Player idle**: 64px (bottom nav only)
- **Player active**: ~126px (bottom nav + mini-bar)

The root shell (`app/root.tsx`) reads `isPlayerVisible` from `useAudioPlayer()` and
sets the CSS custom property on `document.body` via `useEffect`:

```tsx
function ShellLayout() {
  const { isPlayerVisible } = useAudioPlayer();
  const bottomBarHeight = isPlayerVisible ? "126px" : "64px";

  useEffect(() => {
    document.body.style.setProperty("--bottom-bar-height", bottomBarHeight);
    return () => {
      document.body.style.removeProperty("--bottom-bar-height");
    };
  }, [bottomBarHeight]);

  return (
    <div className="flex min-h-screen flex-col justify-between">
      ...
    </div>
  );
}
```

Do NOT set the CSS var via inline `style` on the ShellLayout div. Radix `SheetPortal`
renders into `document.body` as a sibling, not a child of the ShellLayout div. CSS
custom properties only inherit parent→child in the DOM tree, so portal content
cannot see variables set on a sibling element. `document.body` is the lowest common
ancestor.

## Consumers of the Variable

### Sheet component (`ui/sheet.tsx`)

All `side="bottom"` sheets automatically get bottom padding:

```
pb-[calc(var(--bottom-bar-height)+env(safe-area-inset-bottom))]
```

This covers: playlist hero sheet, track-list-item action sheets, and any other
generic `side="bottom"` sheet that needs to clear the bottom chrome.

**Exception — player-context sheets:** Sheets opened from within the player chrome
(QueueSheet, NowPlayingSheet, AddToPlaylist sheet, track actions overflow sheet)
MUST override with `pb-0`. These sheets are opened while the player mini-bar is
visible and have their own height constraints (`h-[80vh]`, `max-h-[85vh]`,
`max-h-[60vh]`) that would be incorrectly shrunk by the auto padding.

```tsx
// QueueSheet
<SheetContent side="bottom" className="h-[80vh] flex flex-col pb-0">
// NowPlayingSheet
<SheetContent side="bottom" className="flex max-h-[85vh] flex-col gap-6 pb-0">
// AddToPlaylist sheet (nested in NowPlaying)
<SheetContent side="bottom" className="flex max-h-[60vh] flex-col pb-0">
// Overflow actions
<SheetContent side="bottom" className="flex flex-col gap-2 pb-0">
```

### Main content area

```
pb-[calc(var(--bottom-bar-height)+env(safe-area-inset-bottom))]
```

Ensures content above the fold isn't hidden behind player + nav.

### Footer

```
pb-[calc(var(--bottom-bar-height)+2rem+env(safe-area-inset-bottom))]
```

Extra 2rem so the copyright text is visible above the chrome.

## Search Page (Special Case)

The search page is a full-screen overlay (`fixed inset-0 z-[80] 100dvh`) that
intentionally covers the bottom nav and player. It does NOT use the CSS variable
because it should occupy the full viewport.

### Autofocus

The search input auto-focuses on every navigation. The approach combines three things:

1. **`location.key`** (not `location.pathname`) as the dependency — React Router assigns
   a new key on every `navigate()` call, even when already on `/search`.

2. **`requestAnimationFrame`** wrapper — the DOM may not be fully settled after SPA
   navigation when the effect fires. `rAF` waits until the next paint frame.

3. **`forwardRef` on Input** — without it, `ref` from `{...props}` spread does NOT
   attach to the underlying `<input>` element. `inputRef.current` will be `null`.

```tsx
const inputRef = useRef<HTMLInputElement>(null);

useEffect(() => {
  requestAnimationFrame(() => {
    inputRef.current?.focus();
  });
}, [location.key]);
```

Do NOT use `setTimeout + document.querySelector` in `bottom-nav.tsx` to focus the
search input. The search page manages its own focus via refs.

### `forwardRef` on Input Component

The shadcn `Input` component (`app/components/ui/input.tsx`) MUST use
`React.forwardRef` so the search page's ref reaches the DOM element.
Use `ComponentPropsWithoutRef` to avoid a double-ref issue where React 19
passes `ref` both through `forwardRef`'s callback AND as a regular prop:

```tsx
const Input = React.forwardRef<HTMLInputElement, React.ComponentPropsWithoutRef<"input">>(
  ({ className, type, ...props }, ref) => (
    <input ref={ref} ... {...props} />
  ),
);
Input.displayName = "Input";
```
