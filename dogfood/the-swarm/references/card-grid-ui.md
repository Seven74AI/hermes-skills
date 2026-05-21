# Card Grid UI Pattern (Expedition & Exploration)

Both ExpeditionPanel and ExplorationPanel use a card grid instead of dropdowns + numeric inputs. This reference documents the pattern.

## Design rationale

Old UI: numeric input for scout count + `<select>` dropdown for destination → confusing UX. Player had to know what each destination gave.

New UI: one card per destination with icon, name, type/yields, and a one-click "Send" button. Player sees everything at a glance.

## HTML structure

```html
<div class="expedition-grid">
  <div class="expedition-card">
    <div class="expedition-card-icon">🌲</div>
    <div class="expedition-card-name">FOREST</div>
    <div class="expedition-card-loot">Wood + Food</div>
    <button class="btn btn-sm">Send</button>
  </div>
  <!-- ... more cards ... -->
</div>
```

## CSS grid

```css
.expedition-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.expedition-card {
  background: rgba(26, 22, 20, 0.6);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.5rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  align-items: center;
}
```

## Active items (expedition row / probe row)

```html
<div class="expedition-row">
  <div class="expedition-row-info">
    <strong>FOREST</strong> <span class="text-muted">1S 1W</span>
  </div>
  <div class="expedition-row-status">
    <span>⏳ 30s</span>
    <span class="risk-low">Risk: 30%</span>
  </div>
</div>
```

Risk color: `.risk-high` (red, >50%) vs `.risk-low` (muted, ≤50%).

## Header pattern

```html
<div class="panel-header">
  <span class="panel-title">🗺️ Expeditions</span>
  <span class="panel-sub">Scouts: 5 · Warriors: 3</span>
</div>
```

Use `.panel-header` and `.panel-sub` for any panel that needs a subtitle showing available resources.

## When no action is possible

Show an italic hint instead of an empty grid:

```html
<div class="exploration-hint">
  Build a spaceship first to explore the cosmos.
</div>
```

```css
.exploration-hint {
  color: var(--text-muted);
  font-size: 0.8rem;
  font-style: italic;
  text-align: center;
  padding: 1rem 0;
}
```

## Implementation notes

- Each card's button listener captures the card's destination via closure
- Buttons are disabled when `canLaunch` is false (no resources, max active, etc.)
- Both panels use `effect()` to re-render when relevant state paths change
- `this.container.innerHTML = ''` on each render (clean rebuild — acceptable for low DOM count)
- No `requestAnimationFrame` or `scheduleRender` — signals handle batching
