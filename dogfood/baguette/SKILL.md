---
name: baguette
description: "BAGUETTE project configuration — FPS rogue-like boulangerie apocalyptique. Godot 4.2 3D, profiles, GitHub, CI pipeline."
version: 1.0.0
metadata:
  hermes:
    tags: [baguette, game, godot, fps, project, kanban]
---

# BAGUETTE — Project Configuration

Quick-reference config. Load this skill when working on the BAGUETTE FPS.

## Concept

**BAGUETTE** — FPS rogue-like 3D. Paris 2087, la dernière boulangerie de France est assiégée. Tu es MITCH, le mitron armé.

Armes : pistolet à baguettes, fusil à croissants, lance-pains au chocolat, four sacré (ultime).
Ennemis : touristes zombies, hipsters sans gluten, critiques gastronomiques, food truck boss.
Décors : rues pavées de Paris, comptoir, farine, pâtisseries.

Scope actuel : PHASE BRAINSTORMING — le concept est une direction, l'équipe doit le raffiner.

## GitHub

`Seven74AI/baguette` — repo fresh, pas de fork upstream.
**CRITICAL: Code MUST be pushed to GitHub.** Kanban scratch workspaces are ephemeral. Every coder task MUST end with `git push origin main`.

## Kanban

Board: `baguette`
Tenant: `baguette`

## Discord

Channel: `#seven-ai`

## Profiles

4 generic profiles: `coder`, `reviewer`, `researcher`, `planner`.

## Godot Validation — MANDATORY

Godot 4.2.2 is installed at `/usr/local/bin/godot4`.

**For every coder task:** the coder MUST run Godot headless and include the output in their handoff comment:

```bash
/usr/local/bin/godot4 --headless --quit 2>&1
```

**For every review:** the reviewer MUST re-run headless validation AND verify the coder included it.

## Testing

**TDD is mandatory.** Load the `test-driven-development` skill for every coder task. Godot projects use GUT (Godot Unit Test) framework. Test files go in `tests/` and are validated by the CI pipeline.

## Common Pitfalls

### Main scene is empty → black screen

The project's `main.tscn` is a bare `Node3D` with no children — launching it yields a black screen (no camera, no lights, no level). The actual playable scene is `scenes/levels/proto/bakery_test.tscn`. If the user reports a black screen, check that `project.godot` has:

```
run/main_scene="res://scenes/levels/proto/bakery_test.tscn"
```

Not `res://scenes/main.tscn`.

### Headless Godot font errors

Godot headless on Linux may emit `ERROR: No loader found for resource` for TTF fonts and GUT GUI themes. These are cosmetic — the test suite still runs. 211 tests, 0 failures confirmed.

### GUT coverage unavailable in headless

GUT 9.3.0 / Godot 4.2 does not support code coverage in headless mode. Use test count + line ratio as proxy metric (current: 211 tests, 4,037 test lines / 4,312 source lines = 90% ratio).

## Known Pitfalls

See `references/pitfalls-and-lessons.md` for:
- Empty main.tscn → black screen fix
- No visual effects despite working code
- Godot 4.2 headless coverage limitations
- Harmless headless errors (fonts, is_inside_tree)

### Coverage

GUT 9.3.0 on Godot 4.2 does **not** support automated code coverage in headless mode. The `-gcover` flag and `coverage: true` config option have no effect. Use line-count ratio as a proxy metric:

```bash
# Source lines
find scenes scripts -name "*.gd" ! -path "*/addons/*" | xargs wc -l

# Test lines
find tests -name "*.gd" | xargs wc -l
```

Current: ~4,300 source / ~4,000 test = ~90% ratio. 211 tests, 0 failures.

### Export for Testing

To send a playable build without the full git history:

```bash
git clone https://github.com/Seven74AI/baguette.git /tmp/baguette-export
rm -rf /tmp/baguette-export/.git
cd /tmp && zip -r baguette.zip baguette-export -x "*.import" "*.godot/imported/*" ".godot/editor/*"
# Send MEDIA:/tmp/baguette.zip to Discord
```

Typical size: ~1.1 MB. User opens in Godot 4.2 editor, launches `scenes/main.tscn`.

## Pipeline

Follow the standard pipeline: researcher → planner → coder → reviewer → done.
Research must complete before planning starts. Planning must complete before coding starts.
Proto phase: validate core loop with minimal scope, then iterate.
