# THE SWARM — DOM Selector Reference

Every selector used in E2E tests. Derived from source: `src/ui/panels/*.ts`, `src/phases/PhaseContent.ts`, `src/main.ts`.

## Phase Indicator

| Element | Selector | Notes |
|---------|----------|-------|
| Phase indicator container | `#phase-indicator` | Shows current phase name |
| Phase text | `#phase-indicator` `.phase-name` | Text content: "The Lonely Queen", "The Colony", "War", "The Expansion" |

## Click & Resources

| Element | Selector | Notes |
|---------|----------|-------|
| Egg click button | `#click-egg` | Main interaction button |
| Egg count | `[data-stat="resources.eggs"]` | Format: "🥚 Eggs: N" |
| Food count | `[data-stat="resources.food"]` | Format: "🍞 Food: N" |
| Larvae count | `[data-stat="resources.larvae"]` | |
| Workers count | `[data-stat="resources.workers"]` | |
| Nest capacity | `[data-stat="resources.nestCapacity"]` | |
| Wood count | `[data-stat="resources.wood"]` | EXPANSION phase only |
| Stone count | `[data-stat="resources.stone"]` | EXPANSION phase only |
| Nectar count | `[data-stat="resources.nectar"]` | EXPANSION phase only |

## Worker Assignment (COLONY+)

| Element | Selector | Notes |
|---------|----------|-------|
| Panel container | `#worker-assignment` | Hidden until colony phase |
| Gather role row | `[data-role="gather"]` | Contains −/count/+ buttons |
| Tend role row | `[data-role="tend"]` | Contains −/count/+ buttons |
| Role count | `.role-count` | Inside `[data-role]` row |
| Plus button | `.role-controls button` (text: "+") | Assigns worker |
| Minus button | `.role-controls button` (text: "−") | Unassigns worker |
| Role controls container | `.role-controls` | Parent of buttons + count |

## Soldier Panel (COMBAT+)

| Element | Selector | Notes |
|---------|----------|-------|
| Panel container | `#soldier-panel` | |
| Recruit Soldier button | `#soldier-panel button` with text "Recruit Soldier" | |
| Training indicator | Text "in training" inside `#soldier-panel` | |
| Soldier stats | `#soldier-panel` `.stat-value` | Strength, Defense, Speed, HP |

## Battle Panel (COMBAT+)

| Element | Selector | Notes |
|---------|----------|-------|
| Scout enemy button | `#scout-enemy` | Reveals enemy info |
| Engage battle button | `#engage-battle` | Disabled until scout done |
| Enemy name display | `#enemy-name` | Populated after scouting |
| Battle result display | `#battle-result` | Shows Victory/Defeat |
| Continue button | `#battle-continue` | After battle resolves |
| Combat log | `#combat-log` | Combat-specific messages |

## Map Panel (EXPANSION)

| Element | Selector | Notes |
|---------|----------|-------|
| Panel container | `.map-panel` or `#map-panel` | Canvas-based map |

## Building Panel (EXPANSION)

| Element | Selector | Notes |
|---------|----------|-------|
| Panel container | `#building-panel` | Class: `building-panel` |
| Barracks row | `[data-building="barracks"]` | Shows level, effects, cost |
| Walls row | `[data-building="walls"]` | Shows level, effects, cost |
| Warehouse row | `[data-building="warehouse"]` | Shows level, effects, cost |
| Building level text | Text "Lv.N" inside row | |
| Building info | `.building-info` | Effect description |
| Building cost | `.building-cost` | Resource cost (🍞🪵🪨🍯) |
| Build button | `button` with text "Build" inside `[data-building]` | Disabled if can't afford |

## Expedition Panel (EXPANSION)

| Element | Selector | Notes |
|---------|----------|-------|
| Panel container | `#expedition-panel` | Class: `expedition-panel` |
| Scout input | `.expedition-input` (first) | type=number |
| Warrior input | `.expedition-input` (second) | type=number |
| Destination select | `.expedition-select` | Options: MEADOW, FOREST, MOUNTAIN |
| Soldier count display | `.soldier-count` | "Scout: N Warrior: N" |
| Launch button | `#expedition-panel button` with text "Launch" | Disabled at max expeditions |
| Active expedition row | `.expedition-row` | Each row: destination + timer |
| Expedition list title | `.expedition-list-title` | "Active Expeditions:" |
| Timers | Text "N⏳ Risk: X%" in `.expedition-row` | |

## Event / Activity Log

| Element | Selector | Notes |
|---------|----------|-------|
| Log container | `#activity-log` or `#event-log` | |
| Log entries | `.log-entry` | Individual narrative/message entries |

## Panel Visibility by Phase

| Phase | Panels Visible |
|-------|---------------|
| EGG_LAYING | `#click-egg`, `#event-log`, `#phase-indicator`, `#resource-panel` |
| COLONY | + `#worker-assignment`, food display |
| COMBAT | + `#soldier-panel`, `#battle-panel`, `#combat-log` |
| EXPANSION | + `.map-panel`, `#building-panel`, `#expedition-panel` |

## E2E Seed Data Pattern

```typescript
// Inject save data BEFORE page load to bypass beforeunload overwrites
await page.addInitScript(() => {
  const data = {
    version: 2,
    timestamp: Date.now(),
    playTimeMs: 0,
    gameState: {
      phase: 'expansion',  // or egg_laying, colony, combat
      resources: {
        eggs: 0, larvae: 0, workers: 20, food: 1000,
        nestCapacity: 100, wood: 300, stone: 200, nectar: 100,
      },
      workersAssigned: { gather: 5, tend: 3, dig: 2, guard: 1 },
      // ... full GameState shape
    },
  };
  localStorage.setItem('the_swarm_save', JSON.stringify(data));
});
await page.goto('/');
await page.waitForTimeout(3000); // Wait for phase transition ticks
```

### Phase transition thresholds
- EGG_LAYING → COLONY: `workers >= 10`
- COLONY → COMBAT: `workers >= 15 && guard >= 1`
- COLONY → EXPANSION: `workers >= 20 && food >= 500`

## Pitfalls

- **`beforeunload` kills seeds:** The game auto-saves on unload. If you set localStorage THEN navigate, the `beforeunload` handler overwrites it. Always use `addInitScript` BEFORE `page.goto`.
- **Phase transitions need ticks:** Wait 2000-3000ms after `page.goto` for transition checks to fire. The game loop ticks every second.
- **Panel visibility ≠ panel existence:** Panels exist in DOM but are `display:none` until their phase. Use `toBeVisible()` not `toBeAttached()` for phase-gated panels.
- **Combat is probabilistic:** RNG is not seeded. Use `toMatch(/Victory|Defeat/)` — never assert a specific outcome.
- **Selectors are stable:** IDs and `data-*` attributes are set in source code. Prefer `#id` and `[data-*]` over class-based selectors which may change.
