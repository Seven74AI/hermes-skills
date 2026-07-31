# agent-browser — Local Browser Testing

Interactive browser testing for the Music Library app via `agent-browser` CLI.

## Setup

```bash
npm i -g agent-browser
agent-browser install              # installs Chrome
agent-browser install --with-deps  # also installs system deps (Linux)
```

## Core Loop

```bash
agent-browser open http://localhost:3000/login --timeout 60000  # SSR is slow, give it time
agent-browser snapshot -i          # interactive elements with @eN refs
agent-browser click @e13           # act on refs
agent-browser snapshot -i          # re-snapshot after any page change
agent-browser close                # clean up
```

## Login Flow

```bash
agent-browser open http://localhost:3000/login --timeout 60000
agent-browser snapshot -i
# Dismiss install banner first
agent-browser click @e13           # "Not now" button (ref varies per session)
agent-browser fill @e8 "kody"
agent-browser fill @e9 "kodylovesyou"
agent-browser click @e9            # focus password field
agent-browser press Enter          # submit (React <Form> needs Enter, not click)
sleep 4
agent-browser snapshot -i          # verify: "Welcome to your music library"
```

## Pitfalls

- **SSR is slow** — first load takes 10-60s on the dev server, up to 90s on the production build. Use `--timeout 60000` on `open`.
- **Hydration stall warning** — `No \`HydrateFallback\` element provided to render during initial hydration` means React hasn't attached event handlers yet. Wait longer. Forms and buttons won't work until this warning stops appearing. On the production build, initial hydration can take 15-30s before the page is interactive.
- **React `<Form>` needs `press Enter`** — clicking the submit button doesn't always trigger form submission. Focus the last field and press Enter instead. The core login sequence is: `fill @e8 "user" → fill @e9 "pass" → click @e9 → press Enter`.
- **Refs are per-snapshot** — they change after navigation, dialogs, or dynamic re-renders. Always re-snapshot before clicking.
- **Fresh browser = no session** — close and re-open to clear login state.
- **Never use curl to bypass auth** — if the browser is available, use it for login. The form has honeypot protection that blocks direct POST requests.
- **Service worker caches old builds** — after `npm run build`, the SW may serve stale JS bundles. Always unregister before testing a new build:
  ```bash
  agent-browser eval "navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()))"
  ```
  Then reload to get fresh assets. Without this, a fixed error may still appear because the browser is running the old build.

## Debugging

```bash
agent-browser console              # see JS errors and warnings
agent-browser eval "window.location.href"  # check current URL
agent-browser screenshot page.png  # visual check
```
