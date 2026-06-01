# One-Shot Cleanup — Fix Stale Ready Tasks Across All Boards

Use when stale tasks exist with NULL skills, NULL max_runtime_seconds,
or PR URLs in bodies. Run once after a major skill or workflow update.

```python
import sqlite3, json, re, os

KANBAN_BASE = '/root/.hermes/kanban/boards'

BOARD_SKILL = {
    'shop': 'shop',
    'the-swarm': 'the-swarm',
    'music-library': 'music-library',
    # ... add new boards
}

_PR_URL_RE = re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+", re.IGNORECASE)

for board in sorted(os.listdir(KANBAN_BASE)):
    db_path = os.path.join(KANBAN_BASE, board, 'kanban.db')
    if not os.path.exists(db_path):
        continue

    conn = sqlite3.connect(db_path)

    base_skills = ['kanban-worker', 'kanban-project-workflow']
    project_skill = BOARD_SKILL.get(board)
    if project_skill:
        base_skills.append(project_skill)
    skills_json = json.dumps(base_skills)

    # 1. Fix NULL skills
    n = conn.execute("""
        UPDATE tasks SET skills = ?
        WHERE status IN ('ready','running','blocked','spawned','failed')
        AND (skills IS NULL OR skills = '' OR skills = '-')
    """, (skills_json,)).rowcount
    if n: print(f"{board}: skills={n}")

    # 2. Fix NULL max_runtime_seconds
    n = conn.execute("""
        UPDATE tasks SET max_runtime_seconds = 3600
        WHERE status IN ('ready','running','blocked','spawned','failed')
        AND max_runtime_seconds IS NULL
    """).rowcount
    if n: print(f"{board}: mrt={n}")

    # 3. Remove PR URLs from bodies (replace with text-only reference)
    for tid, body in conn.execute("""
        SELECT id, body FROM tasks
        WHERE status IN ('ready','running','blocked','spawned','failed')
        AND body LIKE '%github.com%pull%'
    """):
        new_body = _PR_URL_RE.sub(
            lambda m: f"PR ({m.group(0).split('/')[-1]})",
            body
        )
        conn.execute("UPDATE tasks SET body = ? WHERE id = ?", (new_body, tid))
        print(f"{board}: PR URL removed from {tid[:16]} body")

    # 4. Delete PR URL comments (triggers active_pr respawn guard for 24h)
    n = conn.execute("""
        DELETE FROM task_comments
        WHERE task_id IN (SELECT id FROM tasks WHERE status IN ('ready','running','blocked','spawned','failed'))
        AND body LIKE '%github.com%pull%'
    """).rowcount
    if n: print(f"{board}: PR URL comments deleted={n}")

    conn.commit()
    conn.close()
```

Run this after:
- Creating or updating shared skills (`kanban-project-workflow`)
- Changing profile configs (`max_iterations`, `max_spawn`)
- Adding a new board

Run from the main Hermes session (not from a worker — workers don't have
filesystem access to all board DBs).
