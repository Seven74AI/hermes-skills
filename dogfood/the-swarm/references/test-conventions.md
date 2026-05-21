# Test Conventions — Audit & Migration Guide

## The Problem (May 2026 audit)

891 exact-value assertions vs 293 invariants across 39 test files. 75% of tests
encoded hardcoded formula outputs. Every balance change broke 20-30 tests.

## Worst Offenders (before rewrite)

| File | Exact assertions | Invariant | Verdict |
|---|---|---|---|
| TerritorySystem.test.ts | 39 | 0 | Recalculated formula in comments |
| ResourceSystem.test.ts | 35 | 0 | `toBe(9)` instead of `toBeLessThan(10)` |
| BuildingSystem.test.ts | 28 | 0 | Hardcoded cost structs |
| Phase3Integration.test.ts | 26 | 0 | `toBeCloseTo(30)` broke 4× in one session |
| SoldierSystem.test.ts | 19 | 2 | Better but still too exact |

## Before → After Patterns

### Pattern A: Hardcoded output → Resource direction

```ts
// ❌ BEFORE — broke when EGG_HATCH_TIME changed
it('hatches eggs at rate count/EGG_HATCH_TIME', () => {
  state.resources.eggs = 10
  state.eggPipeline = { count: 10, progress: 0 }
  const result = system.tick(state)
  expect(result.resources.eggs).toBe(9)
})

// ✅ AFTER — survives any rate change
it('reduces eggs and increases larvae when pipeline has count', () => {
  const beforeEggs = state.resources.eggs
  const beforeLarvae = state.resources.larvae
  let result = state
  for (let i = 0; i < EGG_HATCH_TIME * 2; i++) {
    result = system.tick(result)
  }
  expect(result.resources.eggs).toBeLessThan(beforeEggs)
  expect(result.resources.larvae).toBeGreaterThan(beforeLarvae)
})
```

### Pattern B: Formula in comment → Behavior assertion

```ts
// ❌ BEFORE
// Rate = 10/10 * (1 + 4*0.25) = 1 * 2 = 2 → 2 eggs hatch
expect(result.resources.larvae).toBe(2)

// ✅ AFTER
expect(withTend.resources.larvae)
  .toBeGreaterThanOrEqual(withoutTend.resources.larvae)
```

### Pattern C: Exact costs → Cost direction

```ts
// ❌ BEFORE
expect(getBuildCost('barracks', 1)).toEqual({food: 100, wood: 50, ...})

// ✅ AFTER
expect(lv2.food).toBeGreaterThan(lv1.food)  // higher levels cost more
expect(cost.food + cost.wood + cost.stone + cost.nectar).toBeGreaterThan(0)  // not free
```

### Pattern D: Exact bonuses → Accumulation direction

```ts
// ❌ BEFORE
expect(result.resources.stone).toBeCloseTo(2.5) // 5 × 0.5

// ✅ AFTER
let result = state
for (let i = 0; i < 3; i++) {
  result = system.tick(result, bonuses)
}
expect(result.resources.stone).toBeGreaterThan(0)  // accumulated
```

## Assertion Cheat Sheet

| Assertion | Use for |
|---|---|
| `toBeGreaterThan(n)` | Resource increased |
| `toBeLessThan(n)` | Resource decreased |
| `toBeGreaterThanOrEqual(n)` | Non-negative check, minimum |
| `toBeLessThanOrEqual(n)` | Capped at max |
| `toBe(true/false)` | Boolean guards |
| `toEqual(before)` | No change (edge case) |
| `not.toBe(before)` | Something changed |
| `toContain('text')` | UI text present |

## NEVER Use

- `toBe(9)` — hardcoded value
- `toBeCloseTo(2.5)` — exact formula output
- `toEqual({food: 100, ...})` — exact cost struct
- Comments that recalculate the formula (they rot immediately)

## Edge Cases to Always Test

Every system should test:
1. Empty/zero: pipeline count=0, workers=0, resources=0
2. Maximum: very large counts (do they handle > capacity?)
3. Conservation: never produce more than input allows
4. Non-negative: resources never go below zero
5. Direction: does X increase Y when expected?

## Files Already Rewritten (commit b624d1c)

- `tests/unit/ResourceSystem.test.ts` — 35→22 assertions, all invariants
- `tests/unit/TerritorySystem.test.ts` — 39→17 assertions, rule-based
- `tests/unit/BuildingSystem.test.ts` — 28→13 assertions, cost direction
- `tests/unit/Phase3Integration.test.ts` — 26→6 assertions, flow verified
- `tests/unit/ResourceSystemTerritory.test.ts` — 15→8 assertions, accumulation

## Files Still Need Work (not yet refactored)

- `tests/unit/SoldierSystem.test.ts` — 19 exact, 2 invariant
- `tests/unit/SpaceshipSystem.test.ts` — has hardcoded cost assertions
- `tests/unit/ExpeditionSystem.test.ts` — has hardcoded loot values
- `tests/unit/BattleSystem.test.ts` — has numeric battle result expectations
