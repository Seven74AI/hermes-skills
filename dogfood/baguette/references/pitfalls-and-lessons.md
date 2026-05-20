# BAGUETTE — Known Pitfalls & Lessons

## Empty main.tscn (Black Screen)

The `scenes/main.tscn` is an empty `Node3D` — no camera, no lights, no level.
Opening the project and pressing F5 gives a black screen.

**Fix:** Change `project.godot` → `run/main_scene` to point to the real level:
```
run/main_scene="res://scenes/levels/proto/bakery_test.tscn"
```

The real playable level is `bakery_test.tscn` (sky, directional light, bakery_main.gd script).

## No Visual Effects When Shooting

The effects code IS present (EffectsManager GPUParticles3D, SoundManager procedural audio),
but visually invisible because:

1. **No 3D weapon model** — the gun is a bare `Node3D` with no visible mesh
2. **Muzzle flash too small** — 5cm box, 0.05s duration, hidden at z=-0.15
3. **Particles too tiny** — scale 0.02-0.06 (2-6cm) at default FOV
4. **All CSG levels** — no textures, no materials, flat colored geometry

211 tests pass, all systems work, but there are zero 3D assets.

## Godot 4.2 Headless Coverage

GUT 9.3.0 on Godot 4.2 does NOT support coverage in headless mode.
The `-gcover` flag is unrecognized. Coverage requires the Godot editor.

**Workaround:** Use test count + ratio as proxy metric.
Current: 211 tests, 0 failures, 35 test files, 90% test/source line ratio.

## Godot 4.2 Headless Errors (Harmless)

Headless test runs produce these non-fatal errors — they don't affect test results:
- `No loader found for resource: .ttf (expected type: FontFile)` — GUT GUI fonts not loaded headless
- `ext_resource referenced non-existent resource` — GUT GUI theme scenes broken headless
- `!is_inside_tree()` — nodes queried before entering scene tree

These are cosmetic. Tests still pass.
