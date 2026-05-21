# Signals Migration Playbook

How THE SWARM migrated from custom Store + StateManager to @preact/signals-core.

## Before → After Cheat Sheet

| Before | After |
|--------|-------|
| `import { Store } from '../../state/Store'` | `import { effect } from '@preact/signals-core'` + `import { gameState } from '../../state/gameSignal'` |
| `store.subscribe('path', cb)` | `effect(() => { void gameState.value.path; cb() })` |
| `store.read('path')` | `gameState.value.path` |
| `manager.getState()` | `gameState.value` |
| `manager.update(newState)` | `gameState.value = newState` |
| `manager.update({ phase: 'colony' })` | `gameState.value = { ...gameState.value, phase: 'colony' }` |
| `new Store(manager)` in beforeEach | `gameState.value = createInitialState()` |
| `getState = () => manager.getState()` | `getState = () => gameState.value` |
| `setState = (s) => manager.update(s)` | `setState = (s) => { gameState.value = s; }` |

## Migration Recipe

### 1. Install
```bash
npm install @preact/signals-core
```

### 2. Create the signal
```ts
// src/state/gameSignal.ts
import { signal } from '@preact/signals-core'
export const gameState = signal<GameState>(createInitialState())
```

### 3. Rewrite main.ts
- Replace `const state = manager.getState()` with `const state = gameState.value`
- Replace `manager.update(newState)` with `gameState.value = newState`
- Remove GameLoop's tick callback (it did a redundant update)
- Fold playTimeMs advancement into the main tick before the single write

### 4. Migrate consumers
For each panel/component:
- Remove `import { Store } from ...` and `import { StateManager } from ...`
- Add `import { effect } from '@preact/signals-core'` and `import { gameState } from '../../state/gameSignal'`
- Replace `store.subscribe('path', callback)` with `effect(() => { void gameState.value.path; callback() })`
- Remove `store` from constructor args
- Replace `store.read('path')` with `gameState.value.path`

### 5. Migrate tests
- Replace `manager = new StateManager(bus); store = new Store(manager)` with `gameState.value = createInitialState()`
- Replace `manager.update({...})` with `gameState.value = { ...gameState.value, ... }`
- Replace `manager.getState()` with `gameState.value`
- Remove `store` from panel constructor calls

### 6. Cleanup
- `Store.ts` and `StateManager.ts` can be deleted (keep for reference during migration)
- `Store.test.ts` and `StateManager.test.ts` can be deleted

## Why This Works Better

1. **Auto-tracking:** effects only re-run when the specific paths they read change. The old Store iterated ALL subscribers every tick.
2. **No comparison bugs:** Signals track by identity of accessed properties, not by `!==` or `shallowEqual` on string paths.
3. **Less code:** ~200 lines of Store + StateManager + shallowEqual → ~20 lines of signal definition.
4. **React-ready:** If we ever move to React, `@preact/signals-react` provides `useSignal()` with zero re-render overhead.

## Pitfalls

- `effect()` callbacks run SYNCHRONOUSLY when the signal changes. Keep them fast.
- The `void gameState.value.field` idiom is needed to register the dependency — just reading `gameState.value` alone tracks the root, which fires on every state change.
- EventBus stays for narrative/cross-cutting events. Don't try to replace `bus.emit('phase_changed')` with signals.
