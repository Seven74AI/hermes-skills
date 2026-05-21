# Ticket Decomposition Recipe

When a ticket bundles multiple independent features, split it into atomic tasks.
This recipe covers the full flow: audit → archive → create → backfill → verify.

## Step 1 — Audit

Identify bundle tickets with `hermes kanban show <id>`. Look for:
- Title contains "+" or commas (e.g., "Research + Conversion Chains")
- Title references multiple GM/UX/feature codes (e.g., "GM-2+GM-3+GM-10")
- Body describes 2+ separate systems with different files
- Effort estimate is L (~8h+) for a single coder task

## Step 2 — Plan the split

Draft the new dependency graph. Each atomic ticket gets ONE feature, ONE set of files.
Independent features → parallel (same parent, no link between them).
Dependent features → chain (child's parent = upstream ticket).

Show the graph to the user before creating. Let them correct dependencies.

## Step 3 — Archive the bundles

```bash
hermes kanban --board <board> archive <bundle_id_1> <bundle_id_2>
```

## Step 4 — Create atomic tickets

ALWAYS include `--max-runtime 3600s --parent <id>`. Title = `[GM-X] Feature Name — short description`.

```bash
# Create parent-first (children depend on its ID)
hermes kanban --board <board> create --assignee coder --max-runtime 3600s --parent <root_id> "[GM-X] Atomic Feature"

# Capture the returned ID for child tickets
hermes kanban --board <board> create --assignee coder --max-runtime 3600s --parent <captured_id> "[GM-Y] Dependent Feature"
```

⚠️ Pitfall: `hermes kanban create` cannot accept `--body` with em-dashes, backticks,
French accents, or single quotes — shell quoting breaks. Create with title only,
then backfill.

## Step 5 — Backfill body + runtime

Tickets created via CLI without `--body` have `body=NULL` in the DB.
Tickets created by the planner may have `max_runtime_seconds=NULL` (fallback ~120s).

```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')

# Fix NULL runtime
for tid in ['t_xxx', 't_yyy']:
    conn.execute('UPDATE tasks SET max_runtime_seconds=3600 WHERE id=?', (tid,))

# Add body (extracted from original bundle's spec)
body = """## Feature Name

### Spec
...

### Files
...

### Testing (TDD)
RUN: terminal("pnpm test:all", background=true, notify_on_complete=true) + process(action="wait", timeout=3600)
"""
conn.execute('UPDATE tasks SET body=? WHERE id=?', (body, tid))

conn.commit()
```

Include in every body:
- `> See docs/UNLOCKS.md for phase mechanics and gameplay context.` (first line)
- Spec section with the feature description
- Files section (New: ..., Modify: ...)
- Testing section with the `pnpm test:all` background+wait command

## Step 6 — Verify the graph

```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')

# Check all todo tickets have runtime + body
for r in conn.execute("""
    SELECT id, max_runtime_seconds, LENGTH(body), title
    FROM tasks WHERE status='todo' ORDER BY id
""").fetchall():
    issues = []
    if not r[1]: issues.append('NO-RUNTIME')
    if not r[2]: issues.append('NO-BODY')
    flag = ' !!' if issues else ''
    print(f'{r[0][:12]} runtime={r[1]}s body={r[2]}B {r[3][:50]}{flag}')

# Check parent/child links
for r in conn.execute("""
    SELECT t.id, t.status,
        (SELECT GROUP_CONCAT(p.id||':'||p.status) FROM task_links tl JOIN tasks p ON tl.parent_id=p.id WHERE tl.child_id=t.id)
    FROM tasks t WHERE t.status IN ('todo','ready')
""").fetchall():
    print(f'[{r[1]:7}] {r[0][:12]} parents: {r[2] or "none"}')

conn.close()
```

## Step 7 — Clean up stale links

After archiving bundles, unlink them from their parents so the dependency graph is clean:

```bash
hermes kanban --board <board> unlink <parent_id> <archived_child_id>
```

## Real case: the-swarm Phase 5 (2026-05-20)

**Before:** 2 bundle tickets blocking 7 downstream tasks
- t_98ea642c: Research System + Resource Conversion Chains (~8h)
- t_d1475cfa: Decision Popups + Automation + Entropy (~8h)

**After:** 5 atomic tickets, 2 parallel workstreams
- t_64eada7d: Research System → t_bed421d2: Resource Conversion Chains
- t_a43c2614: Decision Popups ∥ t_74fe61cd: Automation (parallel)
- t_bb79ef07: Entropy System (child of t_bed421d2, needs darkMatter)

**Gains:** parallel workstreams, focused specs, each task 2-5h instead of 8h bundles.
