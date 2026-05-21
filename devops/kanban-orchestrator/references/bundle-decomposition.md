# Bundle Decomposition: Multi-Feature → Parallel Atomic Tasks

When a ticket bundles multiple independent features (visible from combined tags like
`GM-2+GM-3+GM-10` or `GM-6+GM-4` in the title), split into atomic tasks. Unlike
`task-splitting.md` (single feature → serial chain), this pattern decomposes
INDEPENDENT features into PARALLEL tasks where possible.

## When to Decompose (not chain-split)

- Title contains `+` combining multiple tags: `[GM-6+GM-4]`, `[GM-2+GM-3+GM-10]`
- Body describes 2+ distinct systems/features that don't share files
- Features are conceptually independent (different panels, different systems)
- NOT when features modify the same files — that's a chain-split case

## Step 1: Read All Tickets

```bash
hermes kanban --board <board> show <task_id>
```

Look for:
- Combined tags in title
- Body sections labeled "Part A / Part B / Part C"
- Distinct file lists per feature
- "AND" conjunctions: "Research System AND Resource Conversion Chains"

## Step 2: Map Dependencies Within the Bundle

Some sub-features may genuinely depend on others. Example:

```
[GM-6+GM-4] Research + Conversion Chains
  → Research is standalone
  → Conversion Chains needs Research (unlock via research projects)
  → Split into: R1 (Research) → R2 (Conversion Chains) — serial

[GM-2+GM-3+GM-10] Decisions + Automation + Entropy
  → Decision Popups: standalone UI component
  → Automation: standalone milestone system
  → Entropy: needs darkMatter (which comes from Conversion Chains)
  → Split into: D1 ∥ D2 (parallel, parent=root) + D3 (parent=R2)
```

## Step 3: Archive Original Bundle

```bash
hermes kanban --board <board> archive <bundle_id_1> <bundle_id_2>
```

## Step 4: Create Atomic Sub-Tasks

Create in order: root-level atomics first, then dependencies.

```bash
# Standalone features (parallel-ready)
hermes kanban --board <b> create --assignee coder --max-runtime 3600s --parent <root> "[GM-2] Decision Popups — ..."
hermes kanban --board <b> create --assignee coder --max-runtime 3600s --parent <root> "[GM-3] Automation Upgrades — ..."

# Serial chain
R1=$(hermes kanban --board <b> create --assignee coder --max-runtime 3600s --parent <root> "[GM-6] Research System — ..." | grep -oP 't_\w+')
hermes kanban --board <b> create --assignee coder --max-runtime 3600s --parent "$R1" "[GM-4] Resource Conversion Chains — ..."
```

Always set `--max-runtime 3600s` (from calibration table).

## Step 5: Clean Stale Parent Links

After archiving bundle tickets, the root ticket still has links to archived children.
Unlink them:

```bash
hermes kanban --board <board> unlink <root_id> <archived_bundle_id>
```

## Step 6: Verify the Graph

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
tickets = ['t_xxx', 't_yyy', ...]
for tid in tickets:
    row = conn.execute('SELECT id, status, title FROM tasks WHERE id=?', (tid,)).fetchone()
    parents = conn.execute('SELECT parent_id FROM task_links WHERE child_id=?', (tid,)).fetchall()
    children = conn.execute('SELECT child_id FROM task_links WHERE parent_id=?', (tid,)).fetchall()
    p = ','.join([x[0][:12] for x in parents]) or '-'
    c = ','.join([x[0][:12] for x in children]) or '-'
    print(f'{tid[:12]} [{row[1]:7}] parents=[{p}] children=[{c}] {row[2][:70]}')
conn.close()
"
```

## Real Case: The Swarm Phase 5 (2026-05-20)

Before: 2 bundle tickets
```
t_98ea642c [GM-6+GM-4] Research System + Resource Conversion Chains (~8h)
t_d1475cfa [GM-2+GM-3+GM-10] Decision Density + Automation + Entropy (~8h)
```

After: 5 atomic tickets
```
t_725e77d2 [GM-1] Prestige (root, ~12h)
  ├── t_64eada7d [R1] Research System (5h)
  │     └── t_bed421d2 [R2] Resource Conversion Chains (3h)
  │           └── t_bb79ef07 [D3] Entropy System (3h)
  ├── t_a43c2614 [D1] Decision Popups (2h)  ∥
  ├── t_74fe61cd [D2] Automation Upgrades (3h) ∥  → parallel
  └── t_d33adad7 [S1] Pacing (3h) → t_10a03733 [S2] Offline (5h)
```

Result: D1 and D2 run in parallel with R1. Throughput 2-3× vs original bundle.

## Pitfalls

- **Don't force parallelism where real dependencies exist.** Entropy needed darkMatter → parent=R2, not root. Check body content for cross-feature resource mentions.
- **Clean up stale parent→child links after archive.** t_725e77d2 still lists archived children until `unlink` is called. Unresolved links clutter the graph and confuse audits.
- **Don't lose body content.** If original tickets had detailed specs (file lists, test requirements, formulas), add them as comments on the new sub-tasks. Titles alone may be insufficient.
- **Don't confuse with chain-splitting.** If sub-features touch the same files, use `references/task-splitting.md` instead. Bundle decomposition is for genuinely independent features.
