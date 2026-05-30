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
Also load `kanban-project-workflow` — it contains the shared PR workflow,
respawn guard, profile sync, and worker tuning patterns.

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

## ⛔ Reviewer account pitfall (RESOLVED)

The reviewer agent uses a **GitHub App** (`hermes-sevenai-reviewer`, App ID 3788528)
which provides a separate identity from the coder (`Seven74AI`). The app must have
`Contents: Write` permission — reviews show as `hermes-sevenai-reviewer[bot]` and
count toward branch protection's required approval count. See `kanban-project-workflow`
§ Reviewer agent and `references/github-app-reviewer-setup.md` for the full setup.

## Branch Protection & CI

- **Fork:** `Seven74AI/music-library` — branch protection: `enforce_admins: true`, `required_reviews: 1`, `dismiss_stale_reviews: true`, required checks: `lint, typecheck, vitest, playwright-gate`, auto-merge ON
- **Workflow:** MUST be named `CI` (exact match for branch protection `contexts: ["CI"]`), npm, 2-shard playwright + `playwright-gate` gate job
- **Upstream:** `mnlamart/music-library` — pnpm, PR #9 merged (fix `|| true`)

**⛔ ALL coder tasks MUST include `kanban-project-workflow` in skills.**
Tasks created with `skills=["music-library"]` only will merge red CI because the
coder doesn't know the merge rules. Always use:
```bash
hermes kanban --board music-library create --assignee coder \
  --skills music-library --skills kanban-project-workflow ...
```

## PR Workflow

Same fork model as shop: workers push feature branches to fork → PR → auto-merge → reviewer (GitHub App) approves → squash merge.

## CI

Full CI: `lint` + `typecheck` + `vitest` + `playwright-gate` (consolidates 2 shards into one check)

### Pitfall: `|| true` / `--if-present` — silent CI bypass

Two variants, same effect:

- `pnpm typecheck || true` (shell) — swallows non-zero exit codes
- `npm run typecheck --if-present` (npm) — skips silently if the script doesn't exist

Both make CI report green while type errors pass through.
Fixed upstream in PR #9 but can re-appear after any workflow change. Always verify:
```bash
grep "typecheck" .github/workflows/deploy.yml
# MUST show: pnpm typecheck
# MUST NOT show: pnpm typecheck || true
```

### Pitfall: Emoji CI job `name:` fields break branch protection

GitHub uses the job-level `name:` field as the status check context. If a workflow has
`name: ⬣ ESLint` on the `lint:` job, the check reports as `⬣ ESLint` — but branch
protection requires `lint`. The contexts never match, auto-merge hangs forever.

**Fix:** remove ALL job-level `name:` fields from `.github/workflows/deploy.yml`.
Fixed in `Seven74AI/music-library#2`. Step-level emoji names are fine.

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