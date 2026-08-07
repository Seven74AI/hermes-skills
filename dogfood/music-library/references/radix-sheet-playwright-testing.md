# Radix Sheet + Playwright Testing Pitfalls

## Core issue: `aria-hidden` breaks `getByRole`

Radix UI sheets/dialogs set `aria-hidden="true"` on all sibling elements to the portal container.
Playwright's `getByRole` (and `getByLabel`, etc.) queries the **accessibility tree**, not the raw DOM.
Elements under `aria-hidden` are excluded from the accessibility tree → `getByRole` returns **0 elements**.

**Symptom:** `Error: element(s) not found` even though the element is in the DOM and CSS-visible.

**Why `toBeHidden()` still works:** Playwright considers `aria-hidden` elements as "hidden" for
`toBeHidden()`. So `expect(el).toBeHidden()` passes, but `expect(el).toBeVisible()` fails with
"element(s) not found" — the chained locator resolves to 0 matches.

## Nested sheets: Escape count matters

When a test opens a nested sheet (e.g. overflow sheet inside now-playing sheet):
- One `Escape` closes only the **topmost** sheet
- The outer sheet remains open with `aria-hidden` still active
- The bottom nav (or any element outside sheets) is still inaccessible via `getByRole`

**Wrong:**
```ts
await sheet.getByLabel("More actions").click(); // opens overflow
await page.keyboard.press("Escape");             // closes overflow only
await expect(homeLink).toBeVisible();            // FAILS — main sheet still open
```

**Right:** Press Escape twice, or use `page.locator('css-selector')` to bypass accessibility tree.

## CSS locator workaround — use with caution

CSS selectors like `page.locator('nav[aria-label="Main navigation"] a[href="/"]')` find elements
in the raw DOM, bypassing `aria-hidden`. However:

- `toBeVisible()` on a CSS locator checks CSS visibility, not occlusion. An element behind a
  sheet overlay at a higher z-index will still pass `toBeVisible()`.
- Clicking a CSS-located element that's behind an overlay will hit the overlay instead,
  potentially dismissing the sheet or doing nothing → the test may **hang**.
- **Best practice:** Only use CSS locators when you're certain the element is on top and
  interactive. For sheet-close verification, prefer waiting for the sheet to unmount
  (`data-state` attribute changes) rather than checking elements behind it.

## Recommended approach for sheet interactions

1. Verify the sheet opens: `expect(sheet).toBeVisible()`
2. Verify elements inside the sheet: `expect(sheet.getByRole(...)).toBeVisible()`
3. Verify the sheet covers external elements: `expect(externalLink).toBeHidden()`
4. **Don't try to verify elements are visible after sheet closes via `getByRole`** — if the
   sheet hasn't fully unmounted, `aria-hidden` will still be active. Instead, verify the
   sheet itself is gone: `expect(sheet).toBeHidden()` or check `data-state` attribute.

```ts
// ✅ Good: verify sheet is gone
await page.keyboard.press("Escape");
await page.keyboard.press("Escape");
await expect(sheet).toBeHidden();

// ❌ Avoid: verifying external elements via getByRole after sheet close
await expect(homeLink).toBeVisible(); // may fail if sheet still unmounting
```
