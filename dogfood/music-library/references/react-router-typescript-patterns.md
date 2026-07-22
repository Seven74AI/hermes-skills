# React Router + TypeScript Patterns

## BreadcrumbHandle: never access loaderData properties directly

The `BreadcrumbHandle` Zod schema in `app/components/breadcrumbs.tsx` uses
`z.custom<React.ReactNode>()` as one branch of a union. Under `z.infer`, this
produces `{}` instead of the declared type, making `loaderData` resolve to `{}`
rather than `unknown` inside breadcrumb handlers.

**Do NOT access `loaderData?.album?.name` directly in a `handle` export.**
TypeScript will reject it with `Property does not exist on type '{}'`.

**Instead:** add a `unknown`-accepting helper to `app/utils/breadcrumb-utils.ts`
(following the existing `getTrackTitle` / `getPlaylistTitle` pattern):

```ts
export function getAlbumTitle(data: unknown, fallback = 'Album'): string {
  if (typeof data === 'object' && data !== null && 'album' in data) {
    const d = data as { album?: { name?: string } }
    return d.album?.name || fallback
  }
  return fallback
}
```

Then in the route:

```tsx
import { getAlbumTitle } from '#app/utils/breadcrumb-utils.ts'

export const handle: BreadcrumbHandle = {
  breadcrumb: ({ loaderData }) => getAlbumTitle(loaderData),
}
```

## JSX conditional rendering: verify Prisma field names first

Before applying the ternary fix below, verify the Prisma select field name matches
the schema. Using the wrong field name (e.g. `album` when the schema defines
`albumRecord`) causes the entire `track` type to collapse to `never`, which
cascades through `loaderData` → destructured vars → `.map()` callbacks.

Check the schema with:

```bash
grep -A5 'model Track' prisma/schema.prisma | grep Album
# albumRecord Album? @relation(...)
```

The select field name MUST match the relation name in the Prisma schema.

## JSX conditional rendering: prefer ternary over && for Prisma optional relations

TypeScript's control-flow narrowing with `&&` in JSX can fail for Prisma
optional relation types, producing `never` instead of the narrowed non-null
type (especially when the root cause is a field name mismatch — see above).

**❌ Broken — TypeScript narrows to `never`:**

```tsx
{track.albumRecord && (
  <p>{track.albumRecord.name}</p>   // Property 'name' does not exist on type 'never'
)}
```

**✅ Fixed — ternary narrows correctly:**

```tsx
{track.albumRecord ? (
  <p>{track.albumRecord.name}</p>
) : null}
```

This applies to any Prisma optional relation (e.g. `track.albumRecord`,\n`track.coverImage`) rendered inside JSX conditionals.

## useSubmit over raw form.submit() — preserve React context across navigations

When a server action returns `redirect()`, using native `form.submit()` causes a
full page reload that destroys all React context (including `AudioPlayerProvider`).
Use React Router's `useSubmit()` instead, which performs an SPA fetch — the
router intercepts the redirect and navigates client-side, preserving context.

**❌ Full page reload (loses player state):**

```tsx
const form = document.createElement('form')
form.method = 'post'
// ... append hidden inputs ...
form.submit() // full page POST → 302 redirect → full page reload
```

**✅ Client-side navigation (preserves context):**

```tsx
import { useSubmit } from 'react-router'

const submit = useSubmit()

const confirmDelete = () => {
  void submit({ intent: 'delete' }, { method: 'post' })
  // server returns redirect('/playlists') → intercepted by router → SPA navigation
}
```

## Auto-focus input on every navigation to a route

When a page has an auto-focus `useEffect([], [])`, it only fires on initial mount.
If the user navigates away and back, React Router may reuse the component instance
and the input won't refocus.

**Fix:** depend on `location.key`, not `location.pathname`. React Router assigns
a new key to every navigation — even to the same path — so the effect fires reliably:

```tsx
import { useLocation } from 'react-router'

const location = useLocation()

useEffect(() => {
  inputRef.current?.focus()
}, [location.key])
```

Using `location.pathname` fails when the user clicks the nav tab while already on
the route — the pathname doesn't change, so the effect never fires. `location.key`
handles this case without needing a `setTimeout` + `document.querySelector` hack
in the triggering button.
