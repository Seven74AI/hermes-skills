# Browser Testing Setup

How to run the Music Library app in a real browser for manual testing.

## Prerequisites

The dev server must be running:
```bash
cd ~/projects/music-library
npm run db:seed    # first time only — 31 migrations + seed data
npm run dev        # → http://localhost:3000
```

Wait for "🚀 We have liftoff!"

## Credentials

| Username    | Password       | Role    |
| ----------- | -------------- | ------- |
| `kody`      | `kodylovesyou` | Admin (4 tracks, 2 playlists seeded) |
| `kodyuser`  | `kodylovesyou` | Regular (empty library) |

## Using agent-browser (local Chrome)

The self-hosted Firecrawl at `localhost:3002` does not support browser sessions — use `agent-browser` CLI instead.

### One-time setup
```bash
agent-browser install             # installs Chrome
agent-browser install --with-deps # system deps if needed
```

### Core workflow
```bash
agent-browser open http://localhost:3000/login --timeout 60000
agent-browser snapshot -i           # interactive elements with @eN refs
agent-browser click @e13            # dismiss install banner
agent-browser fill @e8 "kody"       # username
agent-browser fill @e9 "kodylovesyou"  # password
agent-browser press Enter           # submit form (click alone may not work)
sleep 4
agent-browser snapshot -i           # verify logged in
agent-browser close                 # clean up
```

### Navigating between pages
Use `agent-browser open <url> --timeout 60000` for full page loads. In-app navigation via clicking links also works.

### Logging out
Close and re-open the browser — `agent-browser close && agent-browser open ...` gives a fresh session with no cookies.

## Firecrawl self-hosted (not used)

The Firecrawl Docker stack at `/opt/firecrawl` requires `BROWSER_SERVICE_URL=http://playwright-service:3000` in the API container's environment. Even with that set, the playwright service lacks the `/browsers` endpoint needed for browser sessions, so this stack cannot be used for browser automation.
