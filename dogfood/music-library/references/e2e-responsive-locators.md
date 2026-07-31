## Locator pitfalls: responsive visibility

BottomNav (`<nav aria-label="Main navigation">`) has `md:hidden` — invisible
on Playwright's Desktop Chrome viewport (1280x720+).  `getByRole('navigation', { name: 'Main navigation' })` will time out on desktop.

Use viewport-independent locators instead:
- `page.locator("header")` — always present
- `page.getByRole("banner")` — equivalent
- For mobile-specific tests, set `isMobile: true` in the project config or
  use `page.setViewportSize({ width: 375, height: 812 })` in the test.

Other `md:hidden` / responsive elements to watch for:
- `BottomNav` component (navigation shell)
- Any Tailwind `hidden md:block` or `md:hidden` elements

## Locator pitfalls: strict mode violations with `getByText`

When using `getByText(/pattern/i)` on error or boundary pages, the regex can match
multiple elements unexpectedly — Playwright's strict mode will reject the locator
with "strict mode violation: resolved to N elements."

**Common trigger:** Error boundaries that display both a heading AND the URL path
in a `<pre>` tag.  The URL path often contains substrings that match error-related
regex patterns (e.g., `/nonexistent-ssr-test-404` matches `/404/i`).

```ts
// BROKEN — matches both <h1>We can't find this page:</h1> AND
// <pre>/nonexistent-ssr-test-404</pre> (URL path contains "404")
await expect(page.getByText(/can't find this page|not found|404/i)).toBeAttached();

// FIX — pick the first (heading) match
await expect(page.getByText(/can't find this page|not found|404/i).first()).toBeAttached();

// BETTER — use a role-based locator for the heading, which can't match the URL path
await expect(page.getByRole('heading', { name: /can't find this page/i })).toBeAttached();
```

Prefer role-based locators (`getByRole`) over `getByText` regex when the target
element has a clear semantic role — they're immune to accidental URL-path matches.
