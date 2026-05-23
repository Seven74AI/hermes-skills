# Tenant → Skill Auto-Injection (2026-05-22)

## Problem

After the skill-curation pass (128 → 24 skills per profile), dogfood project
skills (shop, the-swarm, music-library, videogame-lab, baguette, glance) were
removed from worker profiles. Tasks with `--skills shop` crashed on dispatch:
"Unknown skill(s): shop".

## Root Cause

Two gaps:
1. Profile skill sync not maintained after reduction — project skills removed
2. No automatic bridge between `--tenant shop` and `--skills shop`

## Fix

Patched `hermes_cli/kanban_db.py` in Two parts:

### 1. `_tenant_project_skill_available()` (new helper, ~55 lines)

- Searches `~/.hermes/skills/` for a `SKILL.md` whose parent directory matches
  the tenant name (e.g. `skills/dogfood/shop/SKILL.md` → skill name `shop`)
- If found, copies the skill into the worker's profile-scoped skills directory
  if it's missing there (uses `shutil.copytree` with `dirs_exist_ok=True`)
- Returns the skill name on success, `None` if no matching skill found

### 2. Dispatch injection (~14 lines in `_build_worker_command`)

After `kanban-worker` is auto-loaded and before per-task skills:

```python
if task.tenant:
    tenant_skill = _tenant_project_skill_available(task.tenant, env.get("HERMES_HOME"))
    if tenant_skill and tenant_skill not in (task.skills or []):
        cmd.extend(["--skills", tenant_skill])
```

Dedup: if the task already has `shop` in its skills list, it's not injected twice.

## Effect

- Tasks with `--tenant shop` automatically get `--skills shop` injected
- Skill is synced into the profile on first dispatch (no more "Unknown skill")
- Zero configuration needed — works for all existing and future tasks
- Non-invasive: tasks without `--tenant` are unaffected

## Edge Cases Tested

| Case | Result |
|------|--------|
| tenant=shop, skills without shop | Auto-injected |
| tenant=shop, skills already has shop | No duplicate |
| tenant=does-not-exist | None returned, nothing injected |
| tenant=None | Skipped entirely |
| tenant=sh (prefix match) | None returned (rglob uses exact dir name) |
| HERMES_HOME=None | Falls back to `~/.hermes` |

## Test Suite

```bash
cd /usr/local/lib/hermes-agent
source venv/bin/activate
python -m pytest tests/hermes_cli/test_kanban_db.py -x -q
# 158 passed (2026-05-22)
```
