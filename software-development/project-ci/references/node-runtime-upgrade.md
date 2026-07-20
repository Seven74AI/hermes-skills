# Node.js Runtime Version Upgrade Checklist

Upgrading Node.js runtime (e.g. 22→24) vs upgrading npm packages — different surface area.

## Places to update

| Surface | Example | Notes |
|---------|---------|-------|
| `package.json` `engines` | `"node": "22"` → `"24"` | Also check `packageManager` if using corepack |
| `package-lock.json` | **Must regenerate** after engines change | Run `npm install --package-lock-only` (or full `npm install`) |
| Dockerfile base image | `FROM node:22-bookworm-slim` → `node:24-bookworm-slim` | Match the OS variant (slim, alpine, etc.) |
| CI workflow `node-version` | `actions/setup-node` `node-version: 22` → `24` | Every job that sets it — grep for all occurrences |
| `.nvmrc` / `.node-version` | `22` → `24` | If present — not all projects have these |
| `@types/node` major version | `@types/node@22` → `@types/node@24` | Can usually bump ahead of runtime safely |

## Verification

After all pins are updated and lockfile regenerated:

1. `npm run typecheck` — type-level compatibility
2. `npm run test -- --run` — unit/integration tests
3. `npm run lint` — linter
4. `npm run build` — production build
5. Production server startup: `MOCKS=true NODE_ENV=production timeout 10 node ./server-build/index.js`
6. E2E: `npm run test:e2e:run` (or CI playwright shards)

## Pitfalls

- **Lockfile staleness.** `package.json` engines change does NOT automatically update `package-lock.json`. The lockfile embeds the engines value at install time. After changing engines, always regenerate: `npm install --package-lock-only`.
- **Don't confuse this with package upgrades.** This is changing the runtime, not updating npm dependencies. The `nodejs-major-upgrades` skill covers package API changes (Express v4→v5, Zod v3→v4); this reference covers the runtime version pin itself.
- **Docker base image tag must be exact.** `node:24` alone is ambiguous (could be any variant). Use the same suffix as the current image (e.g. `-bookworm-slim`, `-alpine`).
- **`--import` hooks must be ESM.** Node 24 is stricter about `--import` hooks. If the project uses `node --import=./path/to/hook.js`, verify the hook is valid ESM (`.mjs` or `"type": "module"`).
