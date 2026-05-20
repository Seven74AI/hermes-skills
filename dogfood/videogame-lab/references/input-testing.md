# Input Testing for Godot Games

Headless validation (`godot4 --headless --quit`) only verifies that the engine loads
and scripts compile. It does NOT test user input. Two complementary defenses catch
UI bugs before they reach the player.

## 1. Input Simulation Tests (GDScript)

Place in `tests/test_input.gd`. Register in `test_runner.gd`'s `_test_files` array.

Pattern: each test calls `GameManager.new_game()` + `AIManager.setup_rivals()`,
then simulates an input by calling the game-logic function directly (e.g.
`gm.try_player_grow_to(target)`) and asserts the expected outcome.

Coverage targets:

| Test | Simulates | Asserts |
|------|-----------|---------|
| Click empty cell | Mouse click on adjacent EMPTY | grow succeeds, cell becomes MYCELIUM, count +1 |
| Click occupied | Click on own cell, tree cell | grow fails, count unchanged, GP unchanged |
| Click tree | Click on tree area | selected_tree_idx updates |
| Click OOB | Click x<0, x>=W, y<0, y>=H | grow fails for all |
| Insufficient GP | GP < GROWTH_COST | grow fails even on valid cell |
| Non-adjacent | Click far from any player cell | grow fails |

Use `gm.DIRS_8` (not DIRS_4) when searching for test targets — the player often
spawns near trees/resources that block orthogonal neighbors.

### Limitations

Cannot test actual `InputEventMouseButton` propagation (headless has no CanvasLayer).
Cannot test Control node `mouse_filter` behavior.

## 2. TSCN Structural Check (ci-validate.sh)

Static analysis that catches Control node configuration bugs before Godot runs.

```bash
# Added to ci-validate.sh BEFORE headless validation
for tscn in $(find "$PROJECT_PATH" -name "*.tscn" -not -path "*/addons/*"); do
    # Check: every Panel/Label node must have mouse_filter=1 (IGNORE)
    # Default mouse_filter=0 (STOP) consumes mouse events → game clicks dead
done
```

Catches: `mouse_filter` defaults, missing `mouse_filter` on new HUD nodes,
regressions from scene edits.

### Extension points

- Check `focus_mode` on buttons (should be NONE if not interactive)
- Check `process_mode` on static labels (should be DISABLED)
- Validate shader `render_mode` strings

## Defense-in-depth

| Layer | What it catches | Runtime needed? |
|-------|----------------|-----------------|
| TSCN structural check | mouse_filter, missing properties | No (static) |
| Godot headless | parse errors, load failures, AStarGrid2D init | Yes (--headless) |
| Input simulation tests | game logic responses to inputs | Yes (--headless) |
| Reviewer playtest | visual glitches, UX feel, actual mouse clicks | Full game window |

The TSCN check + simulation tests together would have caught the proto v3
mouse_filter bug: the structural check would flag `Panel missing mouse_filter`,
and the simulation tests would verify that `try_player_grow_to` logic still works.
