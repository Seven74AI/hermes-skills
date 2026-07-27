# React Router: Every Route Needs a Loader When clientLoader.hydrate Is Active

When any ancestor route has `clientLoader.hydrate: true` (e.g. `root.tsx` using
`defineOfflineClientLoader`), React Router's single-fetch strategy sets
`foundOptOutRoute = true`. This causes the hydration fetch to only include data
for routes that export a `loader`.  **Any route in the matched tree without a
loader is excluded** from the single-fetch response, and the client throws:

```
SingleFetchNoResultError: No result found for routeId "routes/..."
```

This applies to ALL routes — layout routes AND leaf routes. An `ErrorBoundary`
export on the route silently catches the error, making it invisible but still
broken.

## Fix

Add a no-op loader to every route that lacks one:

```tsx
import { data } from "react-router";

export function loader() {
  return data({});
}
```

Layout routes also need `{ data, Outlet }` in the import and `<Outlet />` in
the component.

## Verification script

Run this to find ALL routes missing loaders — do NOT stop after fixing the one
the user reported:

```bash
for f in $(find app/routes -name '*.tsx' -o -name '*.ts' | sort); do
  has_loader=$(grep -c 'export.*function loader' "$f" | tr -d '\n')
  [ -z "$has_loader" ] && has_loader=0
  has_client_loader=$(grep -c 'export.*clientLoader\|defineOfflineClientLoader\|createOfflineClientLoader' "$f" | tr -d '\n')
  [ -z "$has_client_loader" ] && has_client_loader=0
  has_action=$(grep -c 'export.*function action' "$f" | tr -d '\n')
  [ -z "$has_action" ] && has_action=0
  has_default=$(grep -c 'export default' "$f" | tr -d '\n')
  [ -z "$has_default" ] && has_default=0
  if [ "$has_loader" -eq 0 ] && [ "$has_client_loader" -eq 0 ] && [ "$has_action" -eq 0 ] && [ "$has_default" -gt 0 ]; then
    echo "MISSING LOADER: $f"
  fi
done
```

After adding loaders, regenerate types and verify:

```bash
npx react-router typegen
npx tsc --noEmit
```

## Known affected routes (as of 2026-07-26)

| File | Type |
|------|------|
| `app/routes/music.tsx` | Layout |
| `app/routes/music+/services.tsx` | Layout |
| `app/routes/music+/services+/youtube.tsx` | Layout |
| `app/routes/library.tsx` | Layout |
| `app/routes/playlists.tsx` | Layout |
| `app/routes/admin+/_layout.tsx` | Layout |
| `app/routes/settings+/profile.two-factor.tsx` | Layout |
| `app/routes/search.tsx` | Leaf |
| `app/routes/_marketing+/about.tsx` | Leaf |
| `app/routes/_marketing+/privacy.tsx` | Leaf |
| `app/routes/_marketing+/support.tsx` | Leaf |
| `app/routes/_marketing+/tos.tsx` | Leaf |
