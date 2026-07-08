# Deployment CI Gating

## History

Deployment was disabled in two stages:

1. **PR #6** (`821d05c`, 2026-05-29): Soft-disabled `container` and `deploy` jobs by changing `if: ${{ github.event_name == 'push' }}` → `if: false`
2. **PR #12** (`529e428`, 2026-05-30): Removed both jobs entirely (83 lines) since they were dead code

## Jobs removed

**`container`** — built + pushed Docker images to Fly.io registry:
- Staging: `flyctl deploy --build-only --push --image-label $SHA --app {app}-staging` (on `dev` push)
- Production: same + `--build-secret SENTRY_AUTH_TOKEN=...` (on `main` push)

**`deploy`** — deployed pre-built images:
- Staging: `flyctl deploy --image registry.fly.io/{app}-staging:$SHA --app {app}-staging`
- Production: `flyctl deploy --image registry.fly.io/{app}:$SHA`
- Required: `needs: [lint, typecheck, vitest, playwright-gate, container]`

## Re-enabling: `github.repository` self-aware gating

The `deploy.yml` lives in both fork and upstream (same file). The key guard:

```yaml
if: github.repository == 'mnlamart/music-library' && github.event_name == 'push'
```

This makes the file **self-aware** — the deploy jobs only fire when CI runs on the upstream repo on a push event (i.e., on merge, not on PR open).

| Trigger | Running repo | Deploy? |
|---------|-------------|---------|
| Coder pushes to fork branch | `Seven74AI/music-library` | ❌ wrong repo |
| PR opened fork→upstream | `mnlamart/music-library` (but `pull_request` event) | ❌ not a push |
| PR merged into upstream `main`/`dev` | `mnlamart/music-library` + `push` | ✅ deploys |

## Secrets required (upstream only)

- `FLY_API_TOKEN` — Fly.io deploy token
- `SENTRY_AUTH_TOKEN` — for production build arg

The fork doesn't need these secrets since the jobs never execute there.

## Full job YAML (re-enable template)

Append these two jobs at the end of `.github/workflows/deploy.yml`:

```yaml
  container:
    runs-on: ubuntu-24.04
    if: github.repository == 'mnlamart/music-library' && github.event_name == 'push'
    steps:
      - name: ⬇️ Checkout repo
        uses: actions/checkout@v4
        with:
          fetch-depth: 50

      - name: 👀 Read app name
        uses: SebRollen/toml-action@v1.2.0
        id: app_name
        with:
          file: 'fly.toml'
          field: 'app'

      - name: 🎈 Setup Fly
        uses: superfly/flyctl-actions/setup-flyctl@1.5

      - name: 📦 Build Staging Container
        if: github.ref == 'refs/heads/dev'
        run: |
          flyctl deploy \
            --build-only \
            --push \
            --image-label ${{ github.sha }} \
            --build-arg COMMIT_SHA=${{ github.sha }} \
            --app ${{ steps.app_name.outputs.value }}-staging
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

      - name: 📦 Build Production Container
        if: github.ref == 'refs/heads/main'
        run: |
          flyctl deploy \
            --build-only \
            --push \
            --image-label ${{ github.sha }} \
            --build-arg COMMIT_SHA=${{ github.sha }} \
            --build-secret SENTRY_AUTH_TOKEN=${{ secrets.SENTRY_AUTH_TOKEN }} \
            --app ${{ steps.app_name.outputs.value }}
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

  deploy:
    runs-on: ubuntu-24.04
    needs: [lint, typecheck, vitest, playwright-gate, container]
    if: github.repository == 'mnlamart/music-library' && github.event_name == 'push'
    steps:
      - name: ⬇️ Checkout repo
        uses: actions/checkout@v4
        with:
          fetch-depth: 50

      - name: 👀 Read app name
        uses: SebRollen/toml-action@v1.2.0
        id: app_name
        with:
          file: 'fly.toml'
          field: 'app'

      - name: 🎈 Setup Fly
        uses: superfly/flyctl-actions/setup-flyctl@1.5

      - name: 🚀 Deploy Staging
        if: github.ref == 'refs/heads/dev'
        run: |
          flyctl deploy \
            --image "registry.fly.io/${{ steps.app_name.outputs.value }}-staging:${{ github.sha }}" \
            --app ${{ steps.app_name.outputs.value }}-staging
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

      - name: 🚀 Deploy Production
        if: github.ref == 'refs/heads/main'
        run: |
          flyctl deploy \
            --image "registry.fly.io/${{ steps.app_name.outputs.value }}:${{ github.sha }}"
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

## Infrastructure (still in repo)

- `fly.toml` — app name `music-library-5a00`, region `cdg`
- `other/Dockerfile` + `other/Dockerfile.dockerignore`

## Current status

- PR #61 (fork): merged. PR #34 (upstream `mnlamart/music-library`): open.
- Secrets still needed on upstream for deployment to actually work.
