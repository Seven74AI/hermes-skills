# Godot Headless Validation — Server Setup

## Installation

Godot 4.2.2 installed at `/usr/local/bin/godot4` on the Hermes server (vmi3304846).

```bash
# Install (one-time)
cd /tmp
wget -q https://github.com/godotengine/godot-builds/releases/download/4.2.2-stable/Godot_v4.2.2-stable_linux.x86_64.zip
unzip Godot_v4.2.2-stable_linux.x86_64.zip
mv Godot_v4.2.2-stable_linux.x86_64 /usr/local/bin/godot4
chmod +x /usr/local/bin/godot4
```

## Validate a project

```bash
cd /root/videogame-lab/deep-root-proto
/usr/local/bin/godot4 --headless --quit 2>&1
```

Expected output:
```
Godot Engine v4.2.2.stable.official.15073afe3 - https://godotengine.org
WARNING: Started the engine as `root`... (suppress with GODOT_SILENCE_ROOT_WARNING=1)
```

Exit code must be 0. Any `ERROR:` or `FATAL:` is a failure.

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Can't run project: no main scene defined` | `project.godot` missing `run/main_scene` | Add `run/main_scene="res://main.tscn"` under `[application]` |
| `Parser Error: Identifier 'X' is not declared` | Missing variable/method in GDScript | Check the reported line, fix syntax |
| `Can't open file 'res://X'` | Missing file referenced in scene/script | Verify file exists in repo |

## project.godot rewriting pitfall

**NEVER regenerate project.godot from scratch.** When adding new config sections (e.g. `[input]` maps for new controls), use targeted edits. Rewriting the whole file risks dropping:

- `run/main_scene="res://main.tscn"` → game won't launch
- `[input]` action maps → controls break
- `[rendering]` section → rendering may fail
- `[debug]` warning suppressions → noise on every load

This happened with proto v2: coder rewrote project.godot to add new input maps for arrow-key growth, accidentally dropped `run/main_scene`. Game failed to launch despite reviewer approval.

## CI workflow blueprint

```yaml
# .github/workflows/validate.yml
name: Godot Validate
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Godot
        run: |
          wget -q https://github.com/godotengine/godot-builds/releases/download/4.2.2-stable/Godot_v4.2.2-stable_linux.x86_64.zip
          unzip Godot_v4.2.2-stable_linux.x86_64.zip
          chmod +x Godot_v4.2.2-stable_linux.x86_64
      - name: Validate project
        run: ./Godot_v4.2.2-stable_linux.x86_64 --headless --quit --path deep-root-proto 2>&1
```

## Playtest checklist

Before marking any coder task as "ready for review", the coder MUST confirm:
- [ ] `godot4 --headless --quit` exits 0 with no errors
- [ ] Output is included in the handoff comment

Before approving any review, the reviewer MUST:
- [ ] Re-run headless validation (do not trust coder's output alone)
- [ ] Verify `run/main_scene` exists in `project.godot`
- [ ] If any uncertainty → block with "needs runtime validation"

## Playtest checklist (user-side, before GO decision)

- [ ] Game launches and fills the screen (1280×720, no more 300×300)
- [ ] 3 rivals (Red/Orange/Violet) have distinct behaviors
- [ ] 3 trees with independent trades (6 each)
- [ ] Arrow keys + click growth both work
- [ ] Reset (R) works
- [ ] Core loop feels satisfying at 60×40 scale
