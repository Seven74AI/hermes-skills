---
name: music-library
description: "Music Library project configuration — tech stack, repo, tenant."
version: 1.0.0
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

## Status

- PR `mnlamart/music-library#8` merged — consolidates deps, security fix, CONTRIBUTING.md, npm→pnpm CI
- CI verte (Vitest, TypeScript, ESLint, Playwright)
- Board clean
