# .usage.json Corruption Patterns

Diagnosed 2026-05-31. GitHub tracking: https://github.com/Seven74AI/hermes-agent/issues/1

## Schema

`~/.hermes/skills/.usage.json` — sidecar telemetry, one entry per skill name:

```json
{
  "<skill_name>": {
    "created_by": "agent" | null,
    "use_count": 0, "view_count": 0, "patch_count": 0,
    "last_used_at": "ISO", "last_viewed_at": "ISO", "last_patched_at": "ISO",
    "created_at": "ISO",
    "state": "active" | "stale" | "archived",
    "pinned": false,
    "archived_at": null
  }
}
```

Code: `tools/skill_usage.py`

## Known Corruption Patterns

### 1. Directory-prefix leak

Keys stored as `productivity/knowledge-base` or `social-media/xurl` instead of the canonical frontmatter names (`knowledge-base`, `xurl`).

**Cause:** `_mutate()` (L380) records whatever name string callers pass — no normalization to the frontmatter `name:` field. When `skill_view()` or `skill_manage()` is called with a path (`productivity/knowledge-base`), the path leaks into the key.

**Detection:**
```bash
# For each key in .usage.json, check if frontmatter name matches
python3 -c "
import json
with open('$HOME/.hermes/skills/.usage.json') as f:
    data = json.load(f)
for key in data:
    if '/' in key:
        print(f'PREFIXED: {key}')
"
```

### 2. Ghost entries (tracked but not curated)

Skills with `created_by: null` are tracked in usage.json but are invisible to the curator (which only manages `created_by == "agent"` via `_is_curator_managed_record()`). These include:
- Project skills (`shop`, `baguette`, `music-library`, `the-swarm`)
- User-authored skills (`knowledge-base`, `xurl`, `book-extraction`)
- Workflow skills (`kanban-project-workflow`, `project-ci`, `long-running-tests`)

**Cause:** `_mutate()` gates on `is_agent_created()` which excludes only bundled + hub skills. Everything else gets a record, even though the curator only touches `created_by: "agent"`.

**Detection:**
```bash
python3 -c "
import json
with open('$HOME/.hermes/skills/.usage.json') as f:
    data = json.load(f)
ghosts = [k for k,v in data.items() if v.get('created_by') is None]
print(f'{len(ghosts)} ghost entries: {ghosts}')
"
```

### 3. Orphaned keys after skill reorg

When skills move between directories (flat → categorized), old keys persist. Only `forget()` on explicit `skill_manage(delete)` cleans up — moves/renames leave orphans.

**Detection:** cross-reference usage.json keys against on-disk SKILL.md frontmatter names.

### Journal Impact

- Ghost entries inflate entry count → journal may report more "active skills" than reality
- Prefix duplicates split telemetry → `last_used_at` is fractured across keys
- Orphaned keys → journal sees stale skills that don't exist on disk
