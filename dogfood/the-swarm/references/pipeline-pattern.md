# Rate-Based Pipeline Pattern (Paperclips Model)

## Origin

This pattern comes from **Universal Paperclips** — the seminal incremental game where every production system (wire, clips, drones, etc.) uses rate-based pipelines instead of per-item timers.

## Problem

Timer arrays (`eggHatchTimers: [5, 5, 5, 5, 5]`) have three flaws:

1. **O(n) per tick** — must iterate every timer every second
2. **Burst spawning** — all items with identical creation time reach 0 simultaneously
3. **State bloat** — 500 eggs = 500 numbers in the save file

## Solution

```ts
interface Pipeline {
  count: number    // items currently in pipeline
  progress: number // fractional progress accumulated
}

// Each tick:
rate = count / SPAWN_TIME    // e.g., 50 eggs / 5 ticks = 10.0 eggs/tick
progress += rate
completed = Math.floor(progress)
progress -= completed
count -= completed           // items exit the pipeline
```

All three timers (`eggHatchTimers → eggPipeline`, `larvaMatureTimers → larvaPipeline`, `soldierTrainTimers → soldierPipeline`) were replaced.

## Concrete example: 50 eggs, EGG_HATCH_TIME=10

| Tick | count | rate | progress (before) | hatched | progress (after) |
|------|-------|------|-------------------|---------|------------------|
| 1 | 50 | 5.0 | 0.0 + 5.0 = 5.0 | **5** | 0.0 |
| 2 | 45 | 4.5 | 0.0 + 4.5 = 4.5 | **4** | 0.5 |
| 3 | 41 | 4.1 | 0.5 + 4.1 = 4.6 | **4** | 0.6 |
| 4 | 37 | 3.7 | 0.6 + 3.7 = 4.3 | **4** | 0.3 |
| 5 | 33 | 3.3 | 0.3 + 3.3 = 3.6 | **3** | 0.6 |
| ... | ... | ... | ... | ... | ... |

After 5 ticks: ~20 hatched (40%), remaining 30 trickle out over ~10 more ticks. No burst. EGG_HATCH_TIME=10 (balanced for pacing — was 5 but too fast).

## When to use

Use pipelines when:
- Many identical items are created over time
- Each has the same processing duration
- No per-item metadata is needed

Keep timer arrays when:
- Items have different durations
- Per-item metadata is required (destination, type)
- Volume is capped at <10 (expeditions, spaceships)

## Tend workers (multiplier model)

The old flat-bonus formula (`min(tend,count) * 0.2`) was invisible at high egg counts. Replaced with a **multiplier**:

```ts
hatchRate = (count / EGG_HATCH_TIME) * (1 + tendCount * TEND_MULTIPLIER)
// TEND_MULTIPLIER = 0.25 → 4 tend workers always double the rate
```

| Eggs | Tend 0 | Tend 4 | Tend 8 |
|------|--------|--------|--------|
| 10 | 1.0/s | 2.0/s | 3.0/s |
| 100 | 10.0/s | 20.0/s | 30.0/s |
| 1000 | 100.0/s | 200.0/s | 300.0/s |

## CRITICAL Pitfalls

### Downstream pipeline feeding

When one pipeline feeds another (eggs → larvae → workers), **every exit must increment the next pipeline's count**. Forgetting this creates an invisible dead-end.

```ts
// Bug: eggs hatched but larvaPipeline.count never increased → no workers produced
eggs -= actual;
larvae += actual;
eggPipe.count -= actual;
// MISSING: larvaPipe.count += actual  ← THIS WAS THE BUG

// Fix: always feed the downstream pipeline
larvaPipe.count += actual; // hatched eggs enter the larva pipeline
```

**Verification checklist after any pipeline change:**
1. Does `clickEgg()` increment `eggPipeline.count`? ✓
2. Does egg tick decrement `eggPipeline.count` AND increment `larvaPipeline.count`? ✓
3. Does larva tick decrement `larvaPipeline.count` AND increment workers? ✓
4. Does `recruitSoldier()` increment `soldierPipeline.count`? ✓
5. Does soldier tick decrement `soldierPipeline.count` AND increment combatSoldiers? ✓

### Catch-22 resource dependencies

When feature X requires resource Y, but resource Y only comes from feature X, the game is soft-locked. Always provide a **bootstrap path**:

- **Spaceship catch-22 (fixed):** First spaceship required void crystals, but void crystals only came from space exploration (which needs a spaceship). Fix: Lv.1 ship costs only basic resources (food/wood/stone/nectar). Space resources added as rare expedition drops (10% chance per resource).

**Checklist for new features:**
- Is every resource required by a new building/unit PRODUCIBLE before that building/unit is built?
- If not, add a bootstrap path (cheaper first tier, alternative drop source, starting gift)

## Implementation in THE SWARM

- `src/state/GameState.ts` — `Pipeline` interface, three pipeline fields
- `src/systems/ResourceSystem.ts` — `clickEgg()` pushes count, `tick()` runs egg+larva pipelines
- `src/systems/SoldierSystem.ts` — `recruitSoldier()` pushes count, `tick()` runs the pipeline
- `src/persistence/migrations.ts` — v6→v7 converts old arrays to pipelines
- `src/persistence/SaveManager.ts` — SAVE_VERSION = 7
- Spawn times: EGG_HATCH_TIME=10, LARVA_MATURE_TIME=10, SOLDIER_TRAIN_TIME=15
- Full progression doc: `docs/UNLOCKS.md`
