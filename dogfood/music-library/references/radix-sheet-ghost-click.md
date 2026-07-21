# Radix Sheet — Ghost click on overlay dismiss

## Problem

When a Radix `<Sheet>` is dismissed by clicking the overlay (dimmed area), the browser synthesizes a click from that pointerdown. That ghost click lands on whatever element is underneath the now-closed sheet — typically the row/button that opened it, triggering its onClick (e.g., playing a track).

`stopPropagation` on the sheet content doesn't help because portaled content is not a DOM child of the triggering element.

## Fix

Add `onPointerDownOutside` to `SheetContent` that calls `preventDefault()` on the original pointer event:

```tsx
const handlePointerDownOutside = useCallback((event: Event) => {
  if (event instanceof CustomEvent && "originalEvent" in (event.detail ?? {})) {
    (event.detail as { originalEvent: Event }).originalEvent.preventDefault()
  }
}, [])

<SheetContent
  side="bottom"
  onPointerDownOutside={handlePointerDownOutside}
  onPointerDown={handleMenuPointerDown}
  onClick={handleMenuClick}
>
```

- `onPointerDownOutside` fires when user clicks the overlay; `preventDefault()` on the original PointerEvent stops browser click synthesis
- `onPointerDown` on the content catches clicks inside the sheet (same handler)
- `onClick` stops any remaining click propagation
- The sheet still closes normally — only the ghost click is prevented

## Why not `onInteractOutside`?

`onInteractOutside` with `e.preventDefault()` prevents the sheet from closing at all. We want it to close, just without the ghost click.

## References

- https://github.com/radix-ui/primitives/issues/1242
- https://github.com/radix-ui/primitives/issues/2267
- https://github.com/radix-ui/primitives/issues/3099
