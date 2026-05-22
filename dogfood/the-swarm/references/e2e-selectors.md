# E2E Selector Map

ResourcePanel was refactored from `NumberDisplay`-based layout to a multi-section
collapsible HUD. Tests must use the new selectors.

## ResourcePanel — Critical Bar (top row)

| Resource | Selector (container) | Value selector |
|---|---|---|
| Eggs | `[data-stat="resources.eggs"]` | `.critical-value` |
| Larvae | `[data-stat="resources.larvae"]` | `.critical-value` |
| Food | `[data-stat="resources.food"]` | `.critical-value` |
| Soldiers | `.critical-item:nth-child(4)` | `.critical-value` |

Text format: `🥚 5000` (icon + non-breaking space + number).
Old format was `🥚 Eggs: 5000` — the label is gone.

## ResourcePanel — Colony Section

| Resource | Selector |
|---|---|
| Workers | `[data-stat="resources.workers"] .hud-resource-value` |
| Nest capacity | `.progress-bar-fill` or `[role="progressbar"]` |
| Section toggle | `.hud-section.colony-section .section-toggle` |

## Other Panel IDs (unchanged)

| Panel | ID / Selector |
|---|---|
| Worker assignment | `#worker-assignment` |
| Soldier panel | `#soldier-panel` |
| Battle panel | `#battle-panel` |
| Building panel | `#building-panel` |
| Expedition panel | `#expedition-panel` |
| Map panel | `.map-panel` |
| Activity log | `#activity-log` |
| Phase indicator | `#phase-indicator` |
| Click egg button | `#click-egg` |
| Scout button | `#scout-enemy` |
| Engage button | `#engage-battle` |
| Enemy name | `#enemy-name` |
| Battle result | `#battle-result` |
| Battle continue | `#battle-continue` |
| Research panel | `#research-panel` |
| Prestige panel | `#prestige-panel` |
| Spaceship panel | `#spaceship-panel` |
| Space exploration | `#exploration-panel` |

## Worker Assignment

| Element | Selector |
|---|---|
| Role row (gather) | `[data-role="gather"]` |
| Role count | `.role-count` |
| Plus/Minus buttons | `.role-controls button` |
