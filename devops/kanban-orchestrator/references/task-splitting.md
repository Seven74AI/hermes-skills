# Task Splitting: M/L → Atomic Decomposition

When M or L-sized kanban tasks hit repeated timeouts (5+ runs) or budget exhaustion,
split them into 2-3 atomic sub-tasks. Each sub-task should complete in <10 minutes.

## When to Split

- Task has `(M)` or `(L)` in title
- Task has ≥3 runs without completing (check `task_runs` count)
- Task has ≥5 timeout events
- Task scope spans multiple concerns (e.g., "backend + UI + tests")

## Splitting Pattern

### Step 1: Audit

Query the board to identify split candidates:

```python
import sqlite3
conn = sqlite3.connect('/root/.hermes/kanban/boards/<board>/kanban.db')
# M/L tasks with high retry counts
rows = conn.execute('''
    SELECT t.id, t.title, t.status, COUNT(tr.id) as runs
    FROM tasks t LEFT JOIN task_runs tr ON tr.task_id = t.id
    WHERE t.status IN ("running", "ready", "blocked")
      AND (t.title LIKE "%(M)%" OR t.title LIKE "%(L)%")
    GROUP BY t.id HAVING runs >= 3
    ORDER BY runs DESC
''').fetchall()
```

### Step 2: Plan the Decomposition

For each candidate, design 2-3 sub-tasks that form a CHAIN (not parallel):

| Original | Sub-task 1 | Sub-task 2 | Sub-task 3 |
|----------|-----------|-----------|-----------|
| Faceted filters (M) | FTS5 query + index | UI components + state | e2e tests |
| Abandoned cart (M) | DB schema + cron | Email template + Resend | Integration tests |
| Tax engine (L) | Tax rule definitions | Calculation engine | Wire into checkout |
| i18n infrastructure (L) | Locale detection + t() | Hreflang + language picker | Test suite |
| Feature flags (M) | Backend (config+DB) | UI admin panel | Tests + docs |

**Rule**: first sub-task handles infrastructure/schema, middle handles logic/UI,
last handles tests/verification. The chain ensures each step builds on the previous.

### Step 3: Capture Dependencies

Before splitting, record:
- **Parents** of the original task (preserved on sub-task 1)
- **Children** of the original task (relinked to the LAST sub-task)

```python
parents = conn.execute("SELECT parent_id FROM task_links WHERE child_id=?", (tid,)).fetchall()
children = conn.execute("SELECT child_id FROM task_links WHERE parent_id=?", (tid,)).fetchall()
```

### Step 4: Execute the Split

```python
# 1. Reclaim if running
if status == 'running':
    subprocess.run(['hermes', 'kanban', '--board', board, 'reclaim', tid])

# 2. Create sub-tasks in chain
prev_id = None
sub_ids = []
for i, title in enumerate(sub_titles):
    parent_args = []
    if i == 0 and parents:
        for p in parents:
            parent_args.extend(['--parent', p[0]])
    elif prev_id:
        parent_args.extend(['--parent', prev_id])
    
    cmd = ['hermes', 'kanban', '--board', board, 'create',
           '--assignee', 'coder', '--max-runtime', '3600s',
           *parent_args, title]
    result = subprocess.run(cmd, capture_output=True, text=True)
    new_id = parse_task_id(result.stdout)
    sub_ids.append(new_id)
    prev_id = new_id

# 3. Relink children to last sub-task
last_sub = sub_ids[-1]
for child in children:
    subprocess.run(['hermes', 'kanban', '--board', board, 'link', last_sub, child[0]])
    subprocess.run(['hermes', 'kanban', '--board', board, 'unlink', tid, child[0]])

# 4. Archive original
conn.execute("UPDATE tasks SET status='archived', completed_at=? WHERE id=?",
             (int(time.time()), tid))
conn.commit()
```

### Step 5: Verify

Check the dependency chain is intact:

```python
# Verify sub-task chain
for a, b in zip(sub_ids, sub_ids[1:]):
    link = conn.execute("SELECT * FROM task_links WHERE parent_id=? AND child_id=?",
                        (a, b)).fetchone()
    assert link, f"Chain broken: {a} -> {b}"

# Verify children relinked
for child in children:
    link = conn.execute("SELECT * FROM task_links WHERE parent_id=? AND child_id=?",
                        (last_sub, child[0])).fetchone()
    assert link, f"Child {child[0]} not relinked to {last_sub}"
```

## Pitfalls

- **Don't create parallel sub-tasks** — they'd all try to modify the same files simultaneously, causing git conflicts. Use a chain.
- **Don't forget to relink children** — if children stay linked to the archived original, they'll never get promoted (archived parent = dead dependency).
- **Don't relink children to sub-task 1** — they need the final output (sub-task N), not the first step.
- **The `reclaim` command has no `--force` flag** — just `hermes kanban reclaim <id>`. If it says "not running or unknown id", the task isn't `running` from the dispatcher's perspective (even if the DB says so). Fall back to direct SQL: `UPDATE tasks SET status='ready', claim_lock=NULL WHERE id=?`.
- **Archived parent → child auto-promotes** — the kanban dispatcher promotes `todo` children to `ready` when their parent is archived. So children of the archived original will auto-promote. But children relinked to sub-task-N will wait for THAT parent — which is correct.

## Real Cases

- **Shop 2026-05-20**: 9 M/L tasks split into 25 atomic sub-tasks. `t_da062645` (faceted filters, 24 runs) → 3 sub-tasks. `t_c3917d8d` (abandoned cart, 15 runs) → 3 sub-tasks. `t_fb31fc58` (tax engine, P1) → 3 sub-tasks with child `t_4aa79f0a` relinked. All dependency chains verified.
- **Pattern validated**: sub-task 1 inherits original parents, sub-task N inherits original children. Intermediate sub-tasks form a chain. Zero dependency breakage.
