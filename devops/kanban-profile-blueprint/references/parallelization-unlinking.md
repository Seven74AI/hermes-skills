# Parallelization by Unlinking Artificial Dependencies

## Problem

Planners often chain everything behind a single parent ticket (e.g., "Prestige System")
when the actual code dependencies are much looser. Result: 8 tickets run serially
instead of in parallel, wasting `max_spawn` slots.

## Detection

Query the dependency graph and check: does child A *actually* import or depend on
parent B's code? If not, the link is artificial.

```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')

# Show all todo tickets with their parents
for tid, title, parents in conn.execute("""
    SELECT t.id, t.title,
        (SELECT GROUP_CONCAT(p.id||':'||p.status,',') FROM task_links tl
         JOIN tasks p ON tl.parent_id=p.id WHERE tl.child_id=t.id)
    FROM tasks t WHERE t.status='todo'
"""):
    if parents:
        print(f'{tid[:12]} parents=[{parents}]')
```

## Real chains vs artificial chains

**Real chain** (code dependency — must be serial):
- `ResearchSystem → ResourceConversionSystem → EntropySystem`
  (Entropy needs darkMatter, which comes from conversion, which is unlocked by research)

**Artificial chain** (remove it — can be parallel):
- `Prestige → Popups` — Popups are standalone UI, no Prestige imports
- `Prestige → Automation` — Automation is standalone, no Prestige imports
- `Prestige → Pacing` — Pacing is math formulas, no Prestige imports
- `Prestige → Research` — Research is standalone, no Prestige imports

## Unlink recipe

```bash
# Unlink child from parent (parent first, then child)
hermes kanban --board <board> unlink <parent_id> <child_id>

# Example: unlink 4 tickets from Prestige
for tid in t_d33adad7 t_64eada7d t_a43c2614 t_74fe61cd; do
  hermes kanban --board the-swarm unlink t_725e77d2 "$tid"
done
```

When unlinked, children with no remaining parents auto-promote to `ready`
and the dispatcher picks them up immediately.

## After unlinking — verify

```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')

# Each todo ticket should now show only REAL parents
for tid, title, parents in conn.execute("""
    SELECT t.id, t.title,
        (SELECT GROUP_CONCAT(p.id,',') FROM task_links tl
         JOIN tasks p ON tl.parent_id=p.id WHERE tl.child_id=t.id)
    FROM tasks t WHERE t.status IN ('todo','ready','running')
"""):
    parent_list = parents.split(',') if parents else []
    has_only_real = all(not p.startswith('t_725e') for p in parent_list)  # adjust
    print(f'{tid[:12]} parents={len(parent_list)} OK={has_only_real}')
```

## Result: max_spawn utilization

Before unlinking: 1 worker, 7 blocked todo → serial, days to complete.
After unlinking: 5 workers in parallel (max_spawn=5) → hours to complete.

## Real case: the-swarm Phase 5

8 tickets all blocked behind t_725e77d2 (Prestige) because the planner set it as
parent for everything. After unlinking 5 tickets, 4 ran immediately in parallel.
Only 3 genuine chains remained: Research→Conversion→Entropy and Pacing→Offline.
