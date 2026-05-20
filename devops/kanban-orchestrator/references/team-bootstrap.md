# Team Bootstrap — Full Workflow

Complete checklist for creating a new Kanban team from nothing to running ideation pipeline. Use this when the user says "set up a new team for X."

## Phase 1 — Design the roster

Ask the user what roles they need. Push for domain-specific names (not generic `coder`/`researcher`). Example for a game studio:

- `videogame-planner` — project manager / orchestrator
- `game-designer` — mechanics, GDD, player psychology
- `game-coder` — engine, physics, cross-platform perf
- `3d-artist` — modeling, textures, rigging, LODs
- `2d-artist` — sprites, UI, spritesheets
- `sound-designer` — SFX, adaptive audio, music loops
- `game-writer` — narrative, branching dialogue, worldbuilding
- `reviewer` — QA, bug repro, balance, store compliance

Scale decisions: start with 1 per role. Clone on-demand via `hermes profile create <name>-2 --clone-from <name>` when the orchestrator needs parallelism.

## Phase 2 — Create profiles

```bash
for profile in videogame-planner game-designer game-coder 3d-artist 2d-artist sound-designer game-writer reviewer; do
  hermes profile create "$profile" --clone-from default
done
```

**⚠️ Profiles created WITHOUT `--clone-from` have NO `config.yaml`.** They silently fall back to the global default provider (often Anthropic), which may be out of credits or misconfigured. Workers spawned for such profiles crash immediately with API errors. **Fix:** after creating fresh profiles, write a minimal `config.yaml` for each:

```yaml
model:
  default: deepseek-v4-pro
  provider: deepseek
  base_url: https://api.deepseek.com/v1
providers: {}
fallback_providers: []
credential_pool_strategies: {}
toolsets:
- hermes-cli
agent:
  max_turns: 90
  gateway_timeout: 1800
  restart_drain_timeout: 180
  api_max_retries: 3
```

Profiles created with `--clone-from <existing>` DO inherit the source's config.yaml — no manual setup needed for those.

## Phase 3 — Write SOUL.md for each profile

Each SOUL.md should be role-specific: identity, rules, domain knowledge, deliverables format. Key rules of thumb:

- Mobile-first constraints if targeting Android/iOS (framerate budgets, memory limits, touch input)
- Role-specific checklists (export formats, LOD levels, mixing standards, narrative patterns)
- "Rules" section with numbered, enforceable directives
- English for all SOUL.md content (user preference established: French speaker, English working language)

Keep each SOUL.md under 2KB. No fluff, no personality quirks unrelated to the domain.

## Phase 4 — Infrastructure

```bash
# GitHub repo
gh repo create <org>/<team-name> --public \
  --description "Description" --clone

# Kanban board
hermes kanban boards create <team-name>

# Notion page (under root page in notion skill)
# Source .env, use curl with parent.page_id, create markdown page
```

The Notion page should list the team roster and link to the GitHub repo.

## Phase 5 — Launch first pipeline

The ideation pipeline is the standard first task for a new team:

```
T1: <planner>     → Framework (criteria, categories, template) — READY immediately
T2a/b/c: <3 workers> → Parallel idea generation — gated on T1 (--parent T1)
T3: <reviewer>    → Select top N, polish, produce report — gated on all T2
```

Use `hermes kanban --board <name> create` with:
- `--tenant <team-name>` for isolation
- `--assignee <profile>` matching the roster
- `--parent <task_id>` for dependency gates
- `--priority 10` for the planner, 9 for reviewer

## Phase 6 — Delivery

When the pipeline completes, deliver the final report to the user's preferred channel (Discord, Telegram, etc.). If the user asked for a specific platform, use `send_message` with the right target.

## Pitfalls

- **Don't pre-scale profiles.** Create 1 per role, let the orchestrator clone on demand. Pre-creating copies clutters `hermes profile list`.
- **SOUL.md is loaded fresh each message.** No restart needed — write it and it takes effect immediately.
- **Gateway must be running.** Tasks sit in `ready` until a gateway dispatcher picks them up. Check with `hermes gateway status`.
- **Tenant isolation:** always pass `--tenant <name>` to keep tasks from different teams separate.
- **Parent links create gates.** Children with unfinished parents stay in `todo`. The dispatcher auto-promotes to `ready` when all parents reach `done`.
