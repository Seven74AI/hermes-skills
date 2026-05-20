---
name: videogame-lab
description: "Videogame Lab project configuration — profiles, pipeline, repos, Godot validation, GitHub push requirements."
version: 1.5.0
metadata:
  hermes:
    tags: [videogame, project, kanban, reference]
---

# Videogame Lab — Project Configuration

Quick-reference config. Load this skill when working on the game dev pipeline.

## GitHub

`Seven74AI/videogame-lab` — fork from `mnlamart/videogame-lab`

**CRITICAL: Code MUST be pushed to GitHub AND deployed to the project repo.** Kanban scratch workspaces are ephemeral and get cleaned up. The GitHub repo is the source of truth. Every coder task MUST end with `git push origin main` before blocking for review. If the repo is empty, the coder's first step is to initialize it with the proto code.

Additionally: the coder's workspace is NOT the same as the project repo at `/root/videogame-lab/`. Reviewer validates both locations. Code that passes in the workspace but was never deployed to the project repo is a REJECT (see Reviewer Verdict Rules). The coder must sync workspace → project repo before requesting review.

## Kanban

Board: `videogame-lab`
Tenant: `videogame-lab`

## Discord

Channel: `#seven-ai`

## Profiles

4 generic profiles: `coder`, `reviewer`, `researcher`, `planner`.

**Pitfall:** Tasks assigned to a non-existent profile will sit `ready` forever — the dispatcher silently ignores them. Check with `hermes profile list` if a task sits ready for >1h. Fix: `hermes kanban --board <board> reassign <task_id> <existing_profile>`.

## Godot Validation — MANDATORY

Godot 4.2.2 is installed at `/usr/local/bin/godot4` on the server.

**For every coder task:** the coder MUST run Godot headless and include the output in their handoff comment:

```bash
cd /root/videogame-lab/deep-root-proto
/usr/local/bin/godot4 --headless --quit 2>&1
# Expected: "Godot Engine v4.2.2...", exit 0, no ERR/FATAL
# If "Can't run project: no main scene" → project.godot is missing run/main_scene
```

**For every review:** the reviewer MUST re-run headless validation AND verify the coder included it. If missing, reject with "needs Godot headless validation output."

If Godot is not installed → block, don't approve. If impossible, review blocks with "needs runtime validation — human playtest required."

Neither was caught by static review — the game never compiled on Godot 4.2.

## Reviewer Verdict Rules — HARD GATE

Game code reviews have a **mandatory pre-verdict checklist**. The reviewer MUST NOT issue any verdict until ALL checks pass:

| Check | If missing/failing | Verdict |
|-------|-------------------|---------|
| Coder included Godot headless output in handoff | Missing | **REJECT** — "handoff incomplete: missing Godot headless validation output" |
| Reviewer's own `godot4 --headless --quit` passes (exit 0, zero ERR/FATAL) | Fails | **REJECT** — "runtime validation failed: <first error>" |
| All GDScript parse errors resolved | Any found | **REJECT** — "parse errors found: <list>" |
| Test suite passes (if present) | Fails | **NEEDS CHANGES** — "X/Y tests failing" |
| Code quality / architecture | Issues found | **NEEDS CHANGES** — specific file/line feedback |

**APPROVE is only possible when all 5 checks pass.** No exceptions. If the reviewer cannot run Godot (not installed), the ONLY valid verdict is **BLOCK** with "needs runtime validation — human playtest required." Never APPROVE a game task without one of: headless pass, or explicit user playtest confirmation.

This is a HARD GATE because:
- Proto v2 was APPROVED but failed to launch (Vector2i.distance_to, draw_circle parse errors)
- Proto v3 was APPROVED by static review but failed headless (AStarGrid2D init bug)
- Static code inspection is INSUFFICIENT for GDScript — it can parse but fail at runtime
- The reviewer is the LAST LINE OF DEFENSE before the user sees the game

## Common Godot Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Can't run project: no main scene defined` | `project.godot` missing `run/main_scene="res://main.tscn"` in `[application]` | Add the line |
| `Parser Error: ...` | GDScript syntax error | Run `godot --headless --quit` to catch, fix the reported line |
| Project loads but nothing renders | Missing `[rendering]` section or scene has no 2D camera | Add `renderer/rendering_method="forward_plus"` |
| `run/main_scene` lost after config rewrite | Coder regenerates `project.godot` from scratch instead of patching the existing one | **NEVER rewrite project.godot whole-cloth.** Always use targeted edits. The existing file has `run/main_scene`, `[input]` maps, `[rendering]`, and `[debug]` settings that must survive. |
| `SCRIPT ERROR: Parse Error: Cannot find property "distance_to" on base "Vector2i"` | Godot 3→4 migration: `Vector2i` has no `.distance_to()` method (returns float, `Vector2i` is integer-only) | Cast to `Vector2` first: `Vector2(cell_a).distance_to(Vector2(cell_b))` |
| `SCRIPT ERROR: Parse Error: Too many arguments for "draw_circle()" call. Expected at most 3 but received 5.` | Godot 4.x `draw_circle()` signature: `(position, radius, color)` — no more `filled` bool or `width` param | Remove extra args. For filled circles, pass `true` as 4th arg via `draw_circle(pos, r, color, true)` (Godot 4.3+). For outline-only on 4.2, use `draw_arc()` instead. |
| `Failed to load script "res://main.gd" with error "Parse error"` | Catch-all: any parse error in `.gd` file blocks the entire script from loading. The game launches but the scene has an empty script. | Run `godot --headless --quit --path . 2>&1 \| grep -i "SCRIPT ERROR"` to find all parse errors. Fix ALL of them — even one blocks the script. |
| `ERROR: Grid is not initialized. Call the update method.` at `set_point_solid` | Godot 4.2.2 AStarGrid2D bug: setting only `region` before `update()` does not properly size the internal grid. | Workaround: set BOTH `region` AND the deprecated `size` property before `update()`. |
| Mouse clicks not responding on game grid | UILayer CanvasLayer Panel/Labels have default `mouse_filter=STOP` (0), consuming InputEventMouseButton. | Set `mouse_filter = 1` (MOUSE_FILTER_IGNORE) on ALL Control nodes in the HUD. |
| Tiles misaligned — cells render at wrong positions, clicks land on wrong cells | `TileSet.tile_size` defaults to `Vector2i(16,16)`. If game uses 24px cells, TileMap places tiles at 16px spacing but screen_to_cell divides by 24. | Set `ts.tile_size = Vector2i(CELL_SIZE, CELL_SIZE)` in _setup_tileset(). Match it to the game's CELL_SIZE constant. |

## Multi-Worker Parallelization — MANDATORY

When researcher and coder tasks run in parallel on the same board:

1. **Coder MUST read all completed researcher comments** on the board before starting to code. Use `kanban show` on any research task that finished before the coder started.
2. **Create tickets with explicit references** — a proto v3 ticket must list the research ticket IDs whose findings must be applied.
3. **Researcher outputs are inputs for coders.** The researcher produces .md files; the coder implements them. Without this chain, the researcher's work is wasted (proto v2 was approved with zero best practices applied — TileMapLayer, AStarGrid2D, multi-scene, Control Nodes all ignored).

Anti-pattern: researcher and coder ship in parallel, coder never reads research → proto approved but architecturally identical to previous version. This happened with proto v2.

## GUT Setup & Scratch Workspace Pitfalls

Kanban workers get ephemeral scratch workspaces — they start empty. Tasks that download GUT from GitHub each run will **timeout** (~61s for a 60s default limit). GUT is a ~800KB addon with 30+ files; the download + extract pushes past the default timeout.

**Rule: NEVER download GUT in a worker task. Copy it from the host.**

GUT v9.2.1 is installed at `/root/videogame-lab/deep-root-proto/addons/gut/`. Worker's first step:

```bash
cp -r /root/videogame-lab/deep-root-proto/addons/gut addons/
# Instant. No download. No timeout.
```

This pattern was validated on **baguette** (board `baguette`, task `t_9b4d9b4b` — GUT 9.3.0 install + bootstrap tests, 176s, approved) and re-applied to videogame-lab (task `t_037a9a28` — copy + .gutconfig.json + bootstrap test, ~30s estimated).

### Timeout calibration for Godot tasks

| Task type | Recommended `--max-runtime` | Rationale |
|-----------|----------------------------|-----------|
| Copy GUT + config + 1-3 bootstrap tests | 180s (default) | Instant copy, small scope |
| Full GUT suite run (200+ tests) | 300s | Godot headless startup + many assertions |
| Download/install addons from GitHub | **Don't** — copy from host | 61s+ for download alone, exceeds default |
| Deep research (web, analysis, cross-ref) | 600-900s | Research task on the-swarm took 632s |

If a GUT-related task times out repeatedly at 60s, check: is it trying to download GUT? Fix by recreating with the copy-from-host pattern, not by bumping the timeout.

## Server

Godot 4.2.2: `/usr/local/bin/godot4`

See `references/godot-headless-validation.md` for install steps, CI workflow blueprint, common errors, and playtest checklist.

```\nPhase 0: Proto DEEP ROOT ✅ (GO MAIS, 7/10) — 40×25, 1 rival, 1 arbre\nPhase 1: Proto v2 ⚠️ — 60×40, 3 rivals, 3 trees, screen scaling. Has GDScript Godot 3→4 API errors (Vector2i.distance_to, draw_circle args). Fixed run/main_scene but main.gd still has parse errors. Proto v3 is refactoring from scratch with TDD.\n         Roadmap ✅ — 5 phases, ~15 semaines\n         Godot Research ✅ — TileMapLayer, AStarGrid2D, Control Nodes, shaders, save\nPhase 2: Pipeline CI ✅ — Godot headless validation, playtest checklist\n         Proto v3 ✅ — Refactor TDD + best practices (TileMapLayer, A*, shaders, multi-scene)\n         Audio assets ✅ — SFX + 3 music tracks\nPhase 3: Full dev ✅ — 8 feature tickets all done\n         AUDIO ✅ — SFX + musique intégrés\n         TREE REGEN ✅ — 1/60s\n         RIVAL PHASES ✅ — personnalités visibles\n         ZONES ✅ — GP cost modulé\n         CONTINUOUS ✅ — deep root pulse + tree linking\n         END SCREEN ✅ — stats + replay\n         POLISH ✅ — particules, shake, transitions\nPhase 4: Testing 🟡 — 3 test tickets created (suite, input sim, CI pipeline)\n         UI/UX Polish 🟡 — 5 UI/UX tickets created (menu, HUD, flow, end screen, polish global)
## Testing

**TDD is mandatory for proto v3 and all future phases.** Load the `test-driven-development` skill for every coder task. Godot projects use GUT (Godot Unit Test) framework. Test files go in `tests/` and are validated by the CI pipeline.

**Input testing is a separate concern from headless validation.** Headless mode cannot test mouse clicks, Control node mouse_filter, or real input propagation. Two complementary defenses are required:
- **Input simulation tests** (`tests/test_input.gd`): simulate game-logic calls (try_player_grow_to, tree selection) and verify state changes. Registered in `test_runner.gd`.
- **TSCN structural check** (in `ci-validate.sh`): static scan of `.tscn` files for Control nodes with `mouse_filter=STOP` (0) or missing `mouse_filter` — catches the bug before runtime.

See `references/input-testing.md` for the full pattern, coverage targets, and extension points.

See `references/godot-headless-validation.md` for Godot install, CI blueprint, common errors, and playtest checklist.
