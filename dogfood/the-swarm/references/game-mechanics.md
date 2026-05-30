# THE SWARM — Complete Game Mechanics Reference

> Authoritative source. Derived from source code audit, NOT from `docs/UNLOCKS.md`.

**Live URL:** https://seven74ai.github.io/the-swarm/

---

## Architecture

- TypeScript + Vite, Preact Signals (single `signal<GameState>`)
- Ticker: 50ms fixed timestep (20Hz logic) with rAF delta accumulator
- Systems pattern: ResourceSystem, SoldierSystem, BattleSystem, etc.
- Save: localStorage, 2-slot rotating (save + backup), version 11, autosave 30s

---

## Phase Transitions

| From → To | Condition | Panel Unlocks |
|-----------|-----------|---------------|
| EGG_LAYING → COLONY | Workers ≥ 10 | Worker Assignment |
| COLONY → COMBAT | Workers ≥ 15 + 1 Guard | Soldier Panel, Battle Panel |
| COLONY → EXPANSION | Workers ≥ 20 + Food ≥ 500 | Map, Buildings, Expeditions |
| COMBAT → EXPANSION | Workers ≥ 25 + BattlesWon ≥ 3 | Map, Buildings, Expeditions |
| EXPANSION → SPACE | Workers ≥ 30 + Food ≥ 2000 | Spaceship, Exploration |
| SPACE → TRANSCENDENCE | Void Crystals ≥ 50, Antimatter ≥ 10, Dark Matter ≥ 5 | — |

---

## Resources

### Basic (Phase 0+)
| Resource | Source | Rate |
|----------|--------|------|
| Eggs | Click "Lay Egg" | — |
| Larvae | eggPipeline (10s per egg) | depends on pipeline count |
| Workers | larvaPipeline (10s per larva) | depends on pipeline count |
| Food | Unassigned +1/tick, Gather +2/tick | -0.5/tick/worker |

### Territory (Phase 3+)
| Resource | Source | Rate/tick/worker |
|----------|--------|-----------------|
| Wood | FOREST tiles | 0.5 |
| Stone | MOUNTAIN tiles | 0.5 |
| Nectar | MEADOW tiles | 0.5 |

### Space (Phase 4+)
| Resource | Source |
|----------|--------|
| Void Crystals | EUROPA probes, spaceship missions, 10% expedition drop |
| Antimatter | MARS probes, spaceship missions, 10% expedition drop |
| Dark Matter | SATURN probes, spaceship missions, 10% expedition drop |

---

## Workers

| Role | Effect | Requires |
|------|--------|----------|
| Unassigned | +1 food/tick | Always |
| Gather | +2 food/tick | Phase 1 |
| Tend | +25% hatch rate per tender | Phase 1 |
| Guard | Defense + required for COMBAT | Phase 1 |
| Dig | WIP — no effect | Phase 1 |

---

## Two Soldier Systems (completely separate)

### Combat Soldiers — Phase 2
- **File:** `src/systems/SoldierSystem.ts`
- Cost: 5 food + 1 worker → pipeline (SOLDIER_TRAIN_TIME=15 ticks ~15s)
- Usage: auto-battles (BattleSystem, 20 rounds max)
- Equipment: Weapon/Armor upgrades, 10 food × 1.20^level, max Lv.5
- Tracked as `state.combatSoldiers`

### Scouts & Warriors — Phase 3
- **File:** `src/systems/RecruitmentSystem.ts`
- Require Barracks Lv.2 (`if (level >= 2)` — Lv.1 gives NOTHING)
- Scout: 50 food + 1 worker, direct recruitment (no pipeline)
- Warrior: 100 food + 1 worker, direct recruitment (no pipeline)
- Caps: `getEffects('barracks', level)` → scoutsCap=3, warriorsCap=2 at Lv.2+
- Tracked as `state.soldiers.scouts` / `state.soldiers.warriors`
- Usage: expeditions only — NOT combat

---

## Buildings

Formula: `Math.floor(baseCost × 2.5^level)` — exponential.

| Building | Lv.1 Cost | Effect |
|----------|----------|--------|
| Barracks | 100 food, 50 wood | Lv.2+: scoutsCap=3, warriorsCap=2 |
| Walls | 200 stone | +5% defense/level (soft-cap >5) |
| Warehouse | 150 wood, 100 stone | +25 nest capacity/level |

Soft-cap formula: `softCapEffectiveness(value, level)` applies diminishing returns after Lv.5.

---

## Map & Territory (8×8 grid)

### Discovery
1. **DecisionSystem "Scout Report"** — 2-3 min interval, "Investigate" = 1-3 tiles. No scouts needed.
2. **Expeditions** — partial: 1 tile, full success: 2 tiles.
### Claiming

Tile must be: discovered + adjacent to owned tile (8-dir) + not claimed.
`TerritorySystem.claimTile(x, y, state)`.

**Implementation note:** `claimTile()` mutates state in-place. When wiring UI callbacks,
spread `{...state}` before passing to `setState()` to trigger Preact signal re-render.
The MapPanel `onTileClick` callback must be explicitly assigned in UIRoot — it defaults
to `null` and was historically never wired (fixed in a post-launch PR).

### Tile distribution
FOREST 25%, MEADOW 20%, MOUNTAIN 15%, EMPTY 30%, ENEMY_NEST 10%.

---

## Expeditions (Phase 3)

Require scouts/warriors. Max 3 active. RNG: success (soldiers return + full loot + 2 tiles), partial (casualties + half loot + 1 tile), failure (all lost).

| Destination | Soldiers | Loot |
|-------------|----------|------|
| MEADOW 🌼 | scouts | Nectar + Food |
| FOREST 🌲 | scouts | Wood + Food |
| MOUNTAIN ⛰️ | scouts | Stone + Food |

Loot: food = 10 × multiplier, wood/stone = 15 × multiplier, nectar = 10 × multiplier.
10% chance each: +1 voidCrystal, +1 antimatter, +1 darkMatter (space bootstrap).

---

## Spaceship (Phase 4)

Scout ship base cost: 500 food, 200 wood, 200 stone, 100 nectar + 50 voidCrystals + 10 antimatter + 5 darkMatter.

Cost scales: `base × level` (linear, not exponential). Bootstrap: expeditions 10% space resource drops.

Types: scout_ship, cruiser, capital. Efficiency: scout=1.0, cruiser=0.7, capital=0.5.

---

## Exploration (Phase 4)

Probes require scouts + spaceship built. Max 3 active.

| Planet | Type | Primary Yield |
|--------|------|---------------|
| MARS 🪨 | Rocky | Antimatter |
| SATURN 🪐 | Gas | Dark Matter |
| EUROPA 🧊 | Ice | Void Crystals |
| KEPLER-442B 🌍 | Habitable | Food + Void Crystals |

5% space anomaly chance per exploration.

---

## Prestige (Phase 5)

- LP formula: `floor(log10(totalFood) × phaseScore / 100)`
- Bonus: +2% production per LP, +50% per LP on resource formula
- Offline efficiency: 50% base, 75% (Temporal Resonance, 10 LP), 100% (Chrono Synchronization, 5 voidCrystals)
- Entropy: accumulates with darkMatter, max 100, rate 0.1 per darkMatter

---

## Research & Conversion

ResearchSystem: tick-based projects. voidCrystalSynthesis (120t), antimatterContainment (300t), darkMatterDetection (500t).

ResourceConversionSystem: voidCrystals → antimatter → darkMatter DAG. Rate capped by researchers/5, particleLab level, active explorations.

---

## DecisionSystem

Random events every 2-3 min. Types: beetle (+food -worker), overcrowding (expand/cull/wait), scout report (investigate = discover tiles). Auto-dismiss after 30s.

---

## Enemy System

6 enemy types: Red Ant, Termite, Beetle, Wasp, Spider, Mantis. Scaling: +0.5 strength/battle, +2 HP/battle. Loot: food + optional special resources.

---

## Key Timing Constants

| Constant | Value | File |
|----------|-------|------|
| TICK_MS | 50ms (20Hz) | Ticker.ts |
| EGG_HATCH_TIME | 10s | ResourceSystem.ts |
| LARVA_MATURE_TIME | 10s | ResourceSystem.ts |
| SOLDIER_TRAIN_TIME | 15s | SoldierSystem.ts |
| AUTOSAVE_INTERVAL | 30s | SaveManager.ts |
| MAX_ROUNDS | 20 | BattleSystem.ts |
| MAX_ENTRIES | 100 | EventLog.ts |
| DECISION_INTERVAL | 2-3 min | DecisionSystem.ts |
| OFFLINE_CAP | 8h | OfflineProgression.ts |
| PHASE_TRANSITION_ANIM | 3.5s | main.css |
| PANEL_REVEAL | 0.8s | main.css |
| STAGGER_DELAY | 0.15s (2 levels) | main.css |
