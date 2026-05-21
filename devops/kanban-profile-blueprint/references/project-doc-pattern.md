# Project Documentation Pattern

Every board should have a canonical design doc that workers reference for context.
No more "what phase is this?" or "what does the player do here?" blocks.

## The doc

Keep a `docs/UNLOCKS.md` (or `docs/DESIGN.md`) in the project repo with:

1. **Phase transitions** — conditions, required phase, what unlocks
2. **Panels per phase** — what UI appears when
3. **Gameplay loop per phase** — what the player DOES, what they FEEL, key metrics
4. **Resources** — sources, rates, conversion chains
5. **Buildings/units** — costs, effects, unlock conditions

## Ticket references

Every ticket body starts with:
```
> See docs/UNLOCKS.md for phase mechanics and gameplay context.
```

One-liner, costs nothing, tells the worker exactly where to look.

## Why

Workers without phase context will:
- Build features in isolation without understanding where they fit
- Block with "what phase does this go in?"
- Make design decisions that contradict the progression curve
- Create UI that doesn't match the intended player feel

A 5-line Gameplay Loop section (what the player does + feels per phase) gives workers
enough context to make good micro-decisions without blocking.

## Real case: the-swarm (2026-05-20)

`docs/UNLOCKS.md` had phase conditions, panels, units — but no gameplay context.
Added a "Gameplay Loop Per Phase" section with what the player does, feels, and
the key metric for each of 6 phases. Referenced from all 8 todo tickets.

Before: workers blocked with design questions.
After: workers have enough context to build Phase 5 mechanics (automation, research,
entropy) knowing they're part of the "prestige loop, 50h+, clicking is distant memory" feel.
