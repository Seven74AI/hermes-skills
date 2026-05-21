# Idle/Incremental Game Development: Best Practices

Research relevant to THE SWARM (TypeScript, Vite, @preact/signals-core, vanilla DOM).
Full doc at `/root/idle-game-best-practices.md` — this is the condensed version.

---

## 1. Timer & Tick Management

**Use fixed timestep (50ms) with delta accumulator:**

```
const TICK_MS = 50;
let accumulator = 0;

function gameLoop(now) {
  const dt = Math.min(now - lastTime, 1000);
  accumulator += dt;
  while (accumulator >= TICK_MS) {
    tick(TICK_MS / 1000);
    accumulator -= TICK_MS;
  }
  render();
  requestAnimationFrame(gameLoop);
}
```

- Deterministic ticks (same dt every time)
- Built-in offline catch-up (accumulator absorbs background time)
- Frame-rate independent (logic at 20Hz, render at 60/120/144Hz)

**Anti-pattern:** Variable dt passed to every tick — non-deterministic, breaks testing, breaks offline progress.

**Offline progress:** Hybrid approach — closed-form for resource accumulation, accelerated tick for unlocks/events. Cap at 8-24 hours max.

## 2. Resource Management

- **Integers only.** Float64 loses precision above 2^53 (~9 quadrillion). Every major idle game uses integers.
- **break_infinity.js** — standard for numbers up to 1e1e6. Used by Antimatter Dimensions.
- **Two-phase tick:** Compute all rates first (read-only), apply all deltas second (write-only). Prevents order-of-operations bugs.
- **Format only in view layer.** Never format inside game state.
- Anti-pattern: `resource += production` without clamping → negative resources.

## 3. Save/Load Architecture

- **JSON** — universal choice. Human-readable, easy versioning, players can edit saves.
- **Versioned migration chain** — pure functions, frozen forever, never modify old migrations.
- **Rotating backups** — keep 3 save slots (like Cookie Clicker).
- **Corruption recovery** — 3 tiers: parse failure, version too high, invalid state coercion.
- **Auto-save:** every meaningful action + every 60s + beforeunload.
- **Anti-pattern:** Binary serialization. Premature optimization, impossible to debug.

## 4. State Management

- **Single source of truth** is correct. Universal Paperclips: 10K lines, single global object.
- **Anti-pattern:** Distributed signals — multiple `signal()` calls create transient invalid states.
- **Signal write pattern:** Mutate local copy during tick, assign to signal once.
- **Explicit dependency ordering** in tick(): raw → refined → abstract.

## 5. UI Performance

- **Decouple tick rate (20Hz) from render rate (60Hz).**
- **Text node replacement** instead of innerHTML — avoids parse/layout/paint overhead.
- **Dirty-checking:** Skip DOM update if formatted value hasn't changed.
- **Format cache:** Map<number, string>. Avoids Intl.NumberFormat overhead.
- **CSS containment:** `content-visibility: auto` on off-screen panels.
- **Anti-pattern:** innerHTML on every render. Triggers full reflow.

## 6. Testing Strategies

- **Invariant-based testing** (THE SWARM already does this — excellent).
- **Delta-based approximate:** Test direction and bounds, not exact values.
- **Snapshot tests** for save compatibility — fixture saves from every version.
- **Property-based:** Generate random valid states, apply operations, verify invariants.
- **Tick loop determinism:** N ticks at once == 1 tick N times.
- **Anti-pattern:** `expect(value).toBe(42)` — exact value assertions break on every refactor.

## 7. Game-Specific Patterns

| Game | Key Pattern |
|------|-------------|
| Universal Paperclips | Single global state, linear ordered tick, 100ms interval |
| Cookie Clicker | LZString compression, 3 rotating backup slots, version early |
| Antimatter Dimensions | Vuex single store, prestige layer modules, break_infinity.js |
| Kittens Game | All integers, calendar-based ticks, seasonal multipliers |
| Swarm Simulator | Closed-form exponential growth, instant offline computation |

## 8. Concrete Recommendations for THE SWARM

1. **Fixed 50ms timestep** — highest-ROI architectural change
2. **Audit resource clamping** — every resource >= 0 after every tick phase
3. **Format cache** — lightweight Map<number,string> for number display
4. **Offline hybrid** — closed-form resources + accelerated tick for unlocks
5. **Save backup rotation** — keep last 3 saves in localStorage
6. **Snapshot test suite** — save fixtures from every version, load-test on PR
7. **Signal write once** — verify ticks mutate local copy, assign to signal once
8. **Text node rendering** — switch from innerHTML to textContent on standalone text nodes
