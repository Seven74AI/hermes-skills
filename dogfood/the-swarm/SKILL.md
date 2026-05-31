---
name: the-swarm
description: "THE SWARM project configuration — incremental game, Vite/TypeScript, Preact Signals, pipeline mechanics."
version: 3.3.0
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

**⛔ ALL coder tasks MUST include `kanban-project-workflow` in skills.**
Tasks created with `skills=["the-swarm"]` only will merge red CI because the
coder doesn't know the merge rules. Always use:
```bash
hermes kanban --board the-swarm create --assignee coder \
--skill the-swarm --skill kanban-project-workflow ...
```

**Branch protection (Seven74AI/the-swarm):**
- `enforce_admins: true` — even repo owner can't bypass checks
- `required_reviews: 1` — reviewer approval mandatory
- `dismiss_stale_reviews: true` — new push invalidates old approval
- Required checks: `ci` — single CI workflow
- No merge possible without CI green + reviewer approval

## CI

Full CI: `tsc --noEmit + vitest run + playwright test` with 2-shard matrix + playwright-gate.

**Workflow: `.github/workflows/ci.yml`** — 4 jobs: `typecheck`, `vitest`, `playwright` (2-shard matrix), `playwright-gate`.

**Pitfall: `|| true` / `--if-present` — silent CI bypass.** Two variants, same effect:

- `pnpm typecheck || true` (shell) — swallows non-zero exit codes
- `npm run typecheck --if-present` (npm) — skips silently if the script doesn't exist

Both make CI report green while type errors pass through. After any PR, verify the workflow
does NOT have `|| true` on typecheck/lint/test steps:
```bash
grep "typecheck" .github/workflows/ci.yml
# MUST show: tsc --noEmit (or equivalent)
# MUST NOT show: || true
```

### Pitfall: Emoji CI job `name:` fields break branch protection

GitHub uses the job-level `name:` field as the status check context. If a workflow has
`name: ⬣ TypeScript` on the `typecheck:` job, the check reports as `⬣ TypeScript` — but branch
protection requires `ci`. The contexts never match, auto-merge hangs forever on
"waiting for status to be reported."

**Fix:** remove ALL job-level `name:` fields from `.github/workflows/ci.yml`.
The YAML key becomes the context under the unified `ci` workflow.
Step-level emoji names are fine — they're cosmetic inside the job.

Verification:
```bash
gh pr checks <N> --repo Seven74AI/the-swarm
# Must show: ci (NOT ⬣ TypeScript, etc.)
```

## Reviewer account pitfall (RESOLVED)

The reviewer agent uses a **GitHub App** (`hermes-sevenai-reviewer`, App ID 3788528)
which provides a separate identity from the coder (`Seven74AI`). See `kanban-project-workflow`
§ Reviewer agent and `references/github-app-reviewer-setup.md` for the full setup.

## Kanban

- Board: `the-swarm`, tenant: `the-swarm`
- Pipeline: Researcher → Planner → Coder → Reviewer → Done
- Profiles: `coder`, `reviewer`, `researcher`, `planner`

### Task Creation Checklist

When creating swarm tasks, ensure:

```bash
# Coder, reviewer, researcher:
hermes kanban --board the-swarm create \
  --assignee <profile> \
  --max-runtime 3600s \
--skill the-swarm --skill kanban-project-workflow ...
  "<title>"

# Planner (uses kanban-orchestrator, NOT kanban-worker):
hermes kanban --board the-swarm create \
  --assignee planner \
  --max-runtime 3600s \
  --skill kanban-orchestrator --skill kanban-project-workflow --skill the-swarm \
  "<title>"
```

- **Flag is `--skill` (repeatable).** `--skills` (plural) is REJECTED by the CLI. Always use `--skill the-swarm --skill kanban-project-workflow`.
- **skills**: Must include the role skill (`kanban-worker` or `kanban-orchestrator`), `kanban-project-workflow`, and `the-swarm`. Workers without these operate without the shared PR workflow, respawn guard, and project-specific patterns.
- **Planner exception**: planner uses `kanban-orchestrator` instead of `kanban-worker` — it never implements code, it decomposes and delegates.
- **max_runtime_seconds**: Set to 3600 (1h safety net). Heartbeat is the primary liveness signal.
- **Task body**: NEVER include raw GitHub PR URLs (`https://github.com/.../pull/N`). The dispatcher scans all comments for these and blocks respawn for 24h (`active_pr` guard). Use text references like "PR #38" instead.

## Concept

You are an ant queen. Click to lay eggs. Grow your colony. Explore the garden.
Fight or ally. Discover fire. Industrialize. Launch ants into space. Colonize
asteroids. Dyson sphere. Transcend.

6 phases: egg-laying → colony → combat → expansion → space → transcendence.
All implemented. Phase transitions in `src/phases/transitions.ts`.

## Units & Combat System — Two Separate Systems

There are TWO distinct soldier systems — they do NOT overlap:

### Combat Soldiers (SoldierSystem — Phase 2 COMBAT)
- `src/systems/SoldierSystem.ts`
- **Recruitment**: 5 food + 1 worker → pipeline (SOLDIER_TRAIN_TIME=15 ticks, ~15s)
- **Usage**: Auto-battles only (BattleSystem, 20 rounds max)
- **Equipment**: Weapon/Armor upgrades (10 food × 1.20^level, max Lv.5)
- **No subtypes** — these are generic "combat soldiers" (`state.combatSoldiers`)

### Scouts & Warriors (RecruitmentSystem — Phase 3 EXPANSION)
- `src/systems/RecruitmentSystem.ts`
- **Recruitment**: Direct (no pipeline), requires Barracks building
  - Scout: 50 food + 1 worker, Barracks **Lv.2** (`if (level >= 2)` — Lv.1 gives 0 scouts), tracked as `state.soldiers.scouts`
  - Warrior: 100 food + 1 worker, Barracks Lv.2, tracked as `state.soldiers.warriors`
  - Caps Lv.2+: scoutsCap=3, warriorsCap=2 (`getEffects('barracks', level)`)
- **Caps**: `getMaxScouts()` / `getMaxWarriors()` from Barracks level
- **Usage**: Expeditions only (MEADOW, FOREST, MOUNTAIN destinations)
- Combat soldiers are NOT auto-split into scouts/warriors — the two populations are completely independent

### ⛔ Pitfall: UNLOCKS.md Is Unreliable — 6+ Known Errors

`docs/UNLOCKS.md` is a developer reference written early in the project. It is NOT
authoritative — the TypeScript source code is. Known errors (audited 2026-05-29):

1. "soldiers auto-split into scouts/warriors" — wrong. Two separate systems.
2. "Barracks Lv.1 → scouts cap=2" — wrong. Code: `if (level >= 2)`. Lv.1 gives ZERO.
3. Building cost "× level" (linear) — wrong. Formula: `Math.floor(baseCost × 2.5^level)`.
4. Spaceship Lv.1 cost "2000f/500w/500s/200n" — wrong. Scout ship base = 500f/200w/200s/100n.
5. COMBAT_TO_EXPANSION transition missing — code has it (workers≥25, battlesWon≥3).
6. Soldier train time "15 ticks" misleading — with dtSec=0.05 it's ~300 ticks = 15s.

Always verify mechanics against `src/systems/*.ts`, `src/phases/transitions.ts`, and `src/engine/ProgressionCurve.ts`. Never cite UNLOCKS.md without cross-referencing actual code.

- **workerEfficiency curve (2026-05-30):** coefficient 0.001 → 0.0005 in `ProgressionCurve.ts`. Original 0.001 caused starvation at ~1500 workers (efficiency dropped too fast, linear consumption outpaced O(1) production). The 0.0005 coefficient pushes the starvation threshold past the practical game range (~2500 without prestige bonuses). Consumption stays linear (`workers/2`) — NOT multiplied by workerEff (that would be a conceptual regression: workers eating less at higher counts).**

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

- 1158 unit tests (Vitest), 20 E2E specs (Playwright), lint: `tsc --noEmit`
- TDD mandatory — load `test-driven-development` skill
- E2E seed: `page.addInitScript` → `localStorage.setItem('the_swarm_save', ...)` BEFORE `page.goto('/')`
- DOM selectors: `references/dom-selectors.md`
- E2E selectors (post-ResourcePanel refactor): `references/e2e-selectors.md`
- Save version: 11 (migrations cover v1→v11 in `src/persistence/migrations.ts`)

### E2E CI Setup

- **2-shard matrix** in `.github/workflows/ci.yml`: `shard: [1, 2]` with `--shard=${{ matrix.shard }}/${{ strategy.job-total }}`
- **Playwright workers: 2** in CI (`playwright.config.ts:8`), each shard runs 2 browser instances
- **repeat-each=3** for flaky protection
- **playwright-gate** job consolidates shard results
- Branch protection: `typecheck + vitest + playwright-gate` (was monolithic `ci`)
- CI timeout: 60 min per shard

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

- **E2E seeds MUST be pipeline-aware:** eggs in `resources.eggs` are not processed — they must be fed into `eggPipeline.count`. Same for larvae → `larvaPipeline.count`. A seed with `eggs: 3, eggPipeline: { count: 0 }` will never hatch.
- **E2E seeds with incomplete GameState:** old seeds only include a few fields (`version: 2` saves from before the deep-merge fix). `SaveManager.load()` now applies `migrateSave()` + `deepMerge(createInitialState())` so missing fields get defaults. Seeds still work, but always prefer seeding via `createInitialState()`-based overrides rather than raw partial objects.
- **ResourcePanel selectors:** the panel was refactored to a multi-section HUD layout. Resource values use `.critical-item[data-stat="resources.eggs"] .critical-value` (not the old `NumberDisplay` format). Worker count uses `[data-stat="resources.workers"] .hud-resource-value`. See `references/e2e-selectors.md` for the full selector map.
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

## Map & Territory System

8×8 grid (`MapSystem.GRID_SIZE = 8`). Weighted generation: FOREST 25%, MEADOW 20%, MOUNTAIN 15%, EMPTY 30%, ENEMY_NEST 10%.

### Discovery (fog of war)

1. **DecisionSystem "Scout Report"** — event triggers every 2-3 min (random). "Investigate" reveals 1-3 tiles. No scouts needed — bootstrap method.
2. **Expeditions** — partial success: 1 tile, full success: 2 tiles.

### Claiming

Tile must be: discovered + adjacent to an owned tile (8-dir) + not already claimed.
TerritorySystem: `claimTile(x, y, state)`. Each claimed tile = +0.5/tick/worker of its resource type.
First tile requires adjacency — DecisionSystem discovery provides the starting tiles.

### Resources from tiles

| Tile | Resource | Rate |
|------|----------|------|
| FOREST | Wood | 0.5/tick/worker |
| MOUNTAIN | Stone | 0.5/tick/worker |
| MEADOW | Nectar | 0.5/tick/worker |

### ⛔ Pitfall: MapPanel.onTileClick Was Never Wired

MapPanel exposes `onTileClick: ((x: number, y: number) => void) | null` but it was
never assigned in UIRoot or main.ts — defaulted to `null`. Clicking tiles on the
map did nothing (bug present since map was introduced).

**Fix (applied in PR):** In UIRoot's `panelRegistry.set('map_panel', ...)`, capture the
MapPanel instance before returning `getElement()`, then assign `onTileClick`:

```typescript
this.panelRegistry.set('map_panel', () => {
  const mapPanel = new MapPanel(this.mapSystem, this.getState, this.setState);
  mapPanel.onTileClick = (x, y) => {
    const state = this.getState();
    if (this.territorySystem.claimTile(x, y, state)) {
      this.setState({ ...state }); // force signal update (claimTile mutates in-place)
    }
  };
  return mapPanel.getElement();
});
```

**Key details:** `territorySystem.claimTile()` mutates state in-place (replaces tile at
index). Must spread `{...state}` before `setState()` to create a new reference for
Preact signal change detection.

## Building Costs

Formula: `Math.floor(baseCost × 2.5^level)` — exponential, not linear.

| Building | Lv.1 Cost | Lv.2 Cost | Effect |
|----------|----------|----------|--------|
| Barracks | 100 food, 50 wood | 625 food, 312 wood | Lv.2+: scoutsCap=3, warriorsCap=2 |
| Walls | 200 stone | 1250 stone | +5% defense/level (soft-capped >Lv.5) |
| Warehouse | 150 wood, 100 stone | 937 wood, 625 stone | +25 nest capacity/level |

## Game Mechanics Reference

Complete game guide: `references/game-mechanics.md` — phases, transitions, resources, workers, buildings, expeditions, space, prestige, timing constants.

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

## Playtest Tasks

For comprehensive playtest tasks (researcher plays like a real player, focuses on
fun/UX not edge cases), use the template at `references/playtest-task-template.md`.

## Prestige System

- `PrestigeSystem.ts`: `calculateLegacyPoints()` uses `Math.floor(Math.log10(food) * phaseScore / 100)`
- **⚠️ Known issue (#127):** divisor 100 makes prestige tree inaccessible (1 LP needs ~4.6M food). Fix pending: change divisor 100 → 10.
- Prestige requirement: all colony buildings level 5+ AND 100K total food
- Reset: all Phase 1-4 resources, buildings, upgrades, worker counts to starting values
- Legacy Points: +2% production per point (additive)
- Prestige tree: 8 upgrades costing 57 LP total

First spaceship costs only basic resources (food, wood, stone, nectar — zero space resources). Expeditions have 10% chance to drop space resources as alternative bootstrap.

## Phase Transition Animations

3.5s cinematic: overlay with phase name + lore quote, panels reveal one-by-one (0.8s each, 0.15s stagger). Tests must use 3500ms (not 2000ms).

## API Changes (May 2026 audit)

- `PhaseStateMachine.tick()` returns `{ phase, state }` (not just Phase)
- `Transition.onEnter` returns modified state, doesn't mutate
- `SaveManager.load()` chains `migrateSave(data, from, SAVE_VERSION)` then deep-merges with `createInitialState()` so any missing fields get defaults. Old/partial saves (e.g. E2E test seeds with only 10 fields) are safe.
- Ticker uses rAF + 50ms accumulator (was `setInterval`)
- `PLANETS` in shared `src/data/planets.ts`
- `TerritoryBonuses` includes `wood`; FOREST produces wood (not food)
- `formatNumber()` uses commas <1M, M/B suffixes
- EventBus logs errors to `console.error` in dev mode
