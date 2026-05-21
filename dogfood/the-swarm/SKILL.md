---
name: the-swarm
description: "THE SWARM project configuration — incremental game, Vite/TypeScript, Preact Signals, pipeline mechanics."
version: 3.2.0
metadata:
  hermes:
    tags: [the-swarm, game, incremental, web, project]
---

# THE SWARM — Project Configuration

Incremental web game. Load this skill when working on The Swarm.
Also load `kanban-project-workflow` — it contains the shared PR workflow,
respawn guard, profile sync, and worker tuning patterns.

## GitHub — Direct Model

The Swarm uses the **direct model** (`kanban-project-workflow` § GitHub Models):

- Repo: `Seven74AI/the-swarm` (push directly, no upstream fork)
- Deployed at: `https://seven74ai.github.io/the-swarm/` (GitHub Pages, auto-deploy on push)
- Pre-push hook: `.githooks/pre-push` runs `tsc --noEmit` + `vitest run --changed`

## Gating Model

The Swarm uses the **unified PR workflow** from `kanban-project-workflow`:
PR → auto-merge → reviewer agent approves → CI green → GitHub native merge → unblock.
No separate review-gated vs CI-gated — all boards use the same flow.

## Reviewer account pitfall

The reviewer agent uses the same `Seven74AI` GitHub account as the coder.
See `kanban-project-workflow` § Reviewer Agent Needs a Separate GitHub Account.

## Kanban

- Board: `the-swarm`, tenant: `the-swarm`
- Pipeline: Researcher → Planner → Coder → Reviewer → Done
- Profiles: `coder`, `reviewer`, `researcher`, `planner`

### Task Creation Checklist

When creating swarm tasks, ensure:

```bash
hermes kanban --board the-swarm create \
  --assignee <profile> \
  --max-runtime 3600s \
  --skills "kanban-worker,kanban-project-workflow,the-swarm" \
  "<title>"
```

- **skills**: Must include `kanban-worker,kanban-project-workflow,the-swarm`. Workers without these operate without the shared PR workflow, respawn guard, and project-specific patterns.
- **max_runtime_seconds**: Set to 3600 (1h safety net). Heartbeat is the primary liveness signal.
- **Task body**: NEVER include raw GitHub PR URLs (`https://github.com/.../pull/N`). The dispatcher scans all comments for these and blocks respawn for 24h (`active_pr` guard). Use text references like "PR #38" instead.

## Concept

You are an ant queen. Click to lay eggs. Grow your colony. Explore the garden.
Fight or ally. Discover fire. Industrialize. Launch ants into space. Colonize
asteroids. Dyson sphere. Transcend.

7 phases: egg-laying → colony → territory → war/diplomacy → civilization → space → transcendence.
Implemented: 5/7. Phase transitions in `src/phases/transitions.ts`.

## Quick Start

```bash
cd /tmp/the-swarm-check
npm install
npx vite --port 3456 --host 0.0.0.0
```

Access: `http://100.98.177.76:3456` (Tailscale IP, port 3456).

## Tech Stack

- TypeScript 5.5 + Vite 5.4 (build: `tsc && vite build`)
- **@preact/signals-core** — single `signal<GameState>` replaces Store + StateManager
- Vanilla DOM via `UIRoot` + panel classes, no UI framework
- localStorage persistence (`SaveManager` — 3-slot rotating backup)
- Engine: EventBus, Ticker (rAF + 50ms fixed-timestep, 20Hz logic), GameLoop
- Systems: ResourceSystem, SoldierSystem, BattleSystem, MapSystem, TerritorySystem, etc.
- Formatting: `formatNumber()` — commas <1M, M/B suffixes above, format cache

## Testing

- 512 unit tests (Vitest), 7 E2E specs (Playwright), lint: `tsc --noEmit`
- TDD mandatory — load `test-driven-development` skill
- E2E seed: `page.addInitScript` → `localStorage.setItem('the_swarm_save', ...)` BEFORE `page.goto('/')`
- DOM selectors: `references/dom-selectors.md`
- Save version: 7 (migration v6→v7 in `src/persistence/migrations.ts`)

### Test Conventions: Invariants, NOT Hardcoded Values

**CRITICAL:** Test behavior and invariants, never exact numeric outputs.

```ts
// Breaks on any formula change
expect(result.resources.eggs).toBe(9)

// Survives balance changes
expect(result.resources.eggs).toBeLessThan(before)
expect(result.resources.larvae).toBeGreaterThan(before)
expect(result.resources.food).toBeGreaterThanOrEqual(0)
```

See `references/test-conventions.md` for the full audit (891 exact vs 293 invariant).

### Test Pitfalls

- **rAF fake timers:** Ticker uses `requestAnimationFrame`. `vi.useFakeTimers()` doesn't reliably trigger rAF. Test public API, not exact tick counts.
- **Pre-push flaky tests:** Rerun `.githooks/pre-push` manually. If flaky, `git push --no-verify`.
- **Sync tests after API changes:** Run `npx vitest run` after signature changes.

## State Architecture (Preact Signals)

```ts
// src/state/gameSignal.ts
export const gameState = signal<GameState>(createInitialState())
```

- Read: `gameState.value` — synchronous snapshot
- Write: `gameState.value = newState` — triggers all `effect()` callbacks
- Auto-tracking: `effect(() => { void gameState.value.resources.eggs })` only re-runs when eggs change
- One write per tick — always spread, never mutate in place

## Spawn Mechanics: Rate-Based Pipelines

O(1) per tick. Replaces per-item timer arrays.

```ts
interface Pipeline { count: number; progress: number }
// Rate = count / SPAWN_TIME, progress += rate, completed = floor(progress)
```

Three pipelines: `eggPipeline`, `larvaPipeline`, `soldierPipeline`.
Tend workers: multiplier (+25% per worker) on hatch rate.

**Pitfall:** Larva pipeline must be fed — `larvaPipe.count += actual` when eggs hatch.

## UI Panels

Worker Assignment, Resource Panel, Soldier Panel, Building Panel, Map Panel,
Expedition Panel (card grid), Battle Panel, Event Log, Exploration Panel,
Spaceship Panel, Phase Indicator.

## Design Rules

- **Resource Integer Rule:** ALL resources are integers. Use `Math.floor()`.
- **Milestones, NOT flavor text:** EventBus emits on threshold crosses, not every tick.
- **Card grid UI:** ExpeditionPanel, ExplorationPanel. See `references/card-grid-ui.md`.

## Debug and Cheats

```js
// Browser console (F12)
__.getState()
__.setState({ ...__.getState(), resources: { ...s.resources, eggs: 999999, ... } })
__.setState({ ...__.getState(), victoryAchieved: true })
localStorage.setItem('the_swarm_save', '...')
```

## Spaceship Bootstrap

First spaceship costs only basic resources (food, wood, stone, nectar — zero space resources). Expeditions have 10% chance to drop space resources as alternative bootstrap.

## Phase Transition Animations

3.5s cinematic: overlay with phase name + lore quote, panels reveal one-by-one (0.8s each, 0.15s stagger). Tests must use 3500ms (not 2000ms).

## API Changes (May 2026 audit)

- `PhaseStateMachine.tick()` returns `{ phase, state }` (not just Phase)
- `Transition.onEnter` returns modified state, doesn't mutate
- `SaveManager.load()` chains migrations, returns `{ gameState, playTimeMs, timestamp? } | null`
- Ticker uses rAF + 50ms accumulator (was `setInterval`)
- `PLANETS` in shared `src/data/planets.ts`
- `TerritoryBonuses` includes `wood`; FOREST produces wood (not food)
- `formatNumber()` uses commas <1M, M/B suffixes
- EventBus logs errors to `console.error` in dev mode
