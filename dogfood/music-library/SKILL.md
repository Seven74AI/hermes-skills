---
name: music-library
description: "Music Library project configuration — tech stack, repo, tenant."
version: 1.1.0
metadata:
  hermes:
    tags: [music, project, reference]
---

# Music Library — Project Configuration

Load this skill when working on the Music Library app.

## GitHub

`mnlamart/music-library` — remote: `https://oauth2:TOKEN@github.com/Seven74AI/music-library.git`

## Environment

- `MOCKS=true` — all external services mocked
- `GITHUB_TOKEN` in `.env` = **application OAuth** (GitHub login, `api.github.com`), NOT a git push token. Git push uses the remote URL token.

## Working Copy

`/tmp/music-library`

## Tech Stack

- **Framework:** Epic Stack
- **ORM:** Prisma 7 + SQLite
- **Frontend:** React 19 + Tailwind 4
- **Mocks:** `MOCKS=true`

## Branch Protection & CI

- **Fork:** `Seven74AI/music-library` — branch protection: 1 approve + CI (`lint`, `typecheck`, `vitest`, `playwright-gate`), auto-merge ON
- **Workflow:** named `CI`, npm, 2-shard playwright + `playwright-gate` gate job
- **Upstream:** `mnlamart/music-library` — pnpm, PR #9 merged (fix `|| true`)

## PR Workflow

Same fork model as shop: workers push feature branches to fork → PR → auto-merge → reviewer (GitHub App) approves → squash merge.

## CI

Full CI: `lint` + `typecheck` + `vitest` + `playwright-gate` (consolidates 2 shards into one check)

## Pitfalls

- **Package manager divergence:** Fork = npm, upstream = pnpm
- **Reviewer self-approval:** GitHub App may show `authorAssociation: NONE` → admin-merge workaround (see `kanban-project-workflow`)

## Status

- PR `mnlamart/music-library#8` merged — consolidates deps, security fix
- PR `mnlamart/music-library#9` merged — fix `|| true` upstream typecheck
- PR `Seven74AI/music-library#2` merged — fix emoji CI job names
- PR `Seven74AI/music-library#4` merged — playwright-gate + 2-shard standard
- PR `Seven74AI/music-library#1` — cleanup sweep (rebase pending, CI green, awaiting review)
- Board clean (archived=42, done=73)