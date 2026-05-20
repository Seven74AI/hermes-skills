---
name: the-swarm
description: "THE SWARM project configuration — Incremental game from ant queen to interstellar conquest. TypeScript + Vite."
version: 1.1.0
metadata:
  hermes:
    tags: [the-swarm, game, incremental, web, project, kanban]
---

# THE SWARM — Project Configuration

Quick-reference config. Load this skill when working on The Swarm.

## Concept

**THE SWARM** — Incremental web game. You are an ant queen. Click to lay eggs.
Grow your colony. Explore the garden. Fight or ally with other colonies.
Discover fire. Industrialize. Launch ants into space. Colonize asteroids.
Build a Dyson sphere. Transcend.

Planned phases: egg-laying → colony → territory → war/diplomacy → civilization → space → transcendence.
Implemented: 4/7 — EGG_LAYING, COLONY, COMBAT, EXPANSION. Phase transitions defined in `src/phases/transitions.ts`.

TypeScript + Vite SPA. DOM-based rendering. No game engine.

## Quick Start

```bash
cd /tmp/the-swarm-fresh   # or wherever the repo lives
npm install
npx vite --port 3456 --host 0.0.0.0
```

**Access URL:** `http://100.98.177.76:3456` (Tailscale IP, port 3456). Dev server watches files — no manual rebuild. If the dev server isn't running, start it with the command above in background (`terminal(background=true)`).

## GitHub

`Seven74AI/the-swarm` — fresh repo.
**Code MUST be pushed to GitHub.** Every coder task MUST end with `git push origin main`.

## Kanban

Board: `the-swarm`
Tenant: `the-swarm`

## Profiles

4 generic profiles: `coder`, `reviewer`, `researcher`, `planner`.

## Tech Stack

- TypeScript 5.5 + Vite 5.4 (build: `tsc && vite build`)
- No external UI framework — vanilla DOM manipulation via `UIRoot` + panel classes
- All game state in-memory with localStorage persistence (`SaveManager`)
- Systems: ResourceSystem, SoldierSystem, BattleSystem, MapSystem, TerritorySystem, ExpeditionSystem, BuildingSystem, RecruitmentSystem, EnemySystem
- Engine: EventBus, Ticker, GameLoop
- UI: UIRoot + panels (ResourcePanel, SoldierPanel, BuildingPanel, MapPanel, ExpeditionPanel, BattlePanel, EventLog, etc.)
- Phases: PhaseStateMachine + PhaseContent (progressive UI reveal)

## Testing

TDD is mandatory. Load `test-driven-development` skill for every coder task.
- Vitest for unit tests (`npm test`)
- Playwright for E2E tests (`npm run test:e2e`)
- Lint: `tsc --noEmit`
- 400+ unit tests, 14 E2E tests across `tests/e2e/game.spec.ts`, `combat.spec.ts`, `phase3-expansion.spec.ts`
- E2E seed pattern: inject game state via `page.addInitScript` → `localStorage.setItem('the_swarm_save', JSON.stringify(data))` BEFORE `page.goto('/')`. This bypasses `beforeunload` overwrites.
- All DOM selectors documented in `references/dom-selectors.md` — load that file before writing any e2e test.

## Pipeline

Researcher → Planner → Coder → Reviewer → Done.