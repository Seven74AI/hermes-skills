# Batch Issue-to-Kanban Workflow

How to create kanban tasks from GitHub issues with dependency links in one shot.

## When to use

When a project has many GitHub issues (50+) with structured `Blocks:` / `Blocked by:` metadata, and you want to mirror them as kanban tasks with correct blocking relationships.

## Steps

### 1. Read the INDEX issue first

Always read the master tracking issue (e.g. `#167`) BEFORE creating tickets. It defines:
- Phase ordering rules
- Dependency hotspots
- Cross-cutting guardrails
- Agent dispatch rules

### 2. Extract semantic ID → GitHub number mapping

Issues use semantic IDs like `P1.1.1`, `P1.1.2` in their `Blocks:` and `Blocked by:` fields. Parse titles with regex `P\d+(?:\.\d+)+` to build the map:

```python
import re, json, subprocess

issues = json.loads(subprocess.run(
    ["gh", "issue", "list", "--repo", "mnlamart/shop", "--state", "open",
     "--limit", "100", "--json", "number,title,body"],
    capture_output=True, text=True
).stdout)

sem_to_num = {}
for issue in issues:
    m = re.search(r'\b(P\d+(?:\.\d+)+)\b', issue["title"])
    if m:
        sem_to_num[m.group(1)] = issue["number"]
```

### 3. Parse dependencies from issue bodies

Issues have lines like:
```
**Blocks:** P1.1.2, P1.1.4, P1.1.5
**Blocked by:** P1.1.1
```

Parse both directions to build the dependency graph:

```python
deps = {}  # blocker_num → [blocked_nums]
for issue in issues:
    num = issue["number"]
    body = issue.get("body", "")
    
    blocks_match = re.search(r'\*\*Blocks:\*\*\s*(.*)', body)
    if blocks_match:
        text = blocks_match.group(1).strip()
        for pid in re.findall(r'P\d+(?:\.\d+)+', text):
            if pid in sem_to_num:
                deps.setdefault(num, []).append(sem_to_num[pid])
    
    blocked_by_match = re.search(r'\*\*Blocked by:\*\*\s*(.*)', body)
    if blocked_by_match:
        text = blocked_by_match.group(1).strip()
        for pid in re.findall(r'P\d+(?:\.\d+)+', text):
            if pid in sem_to_num:
                blocker = sem_to_num[pid]
                deps.setdefault(blocker, []).append(num)
```

### 4. Create kanban tasks

Use `hermes kanban --board <board> create` for each issue. Include the GitHub number in the title for traceability:

```python
for num in sorted(issues_by_phase[phase]):
    title = f"[#{num}] {issue_title}"
    subprocess.run(["hermes", "kanban", "--board", "shop", "create", title])
```

### 5. Map GitHub numbers to kanban task IDs

After creation, parse `hermes kanban --board <board> list` to extract `t_xxxxxxxx` IDs:

```python
gh_to_task = {}
for line in kanban_output.split('\n'):
    m = re.search(r'(t_\w+).*\[#(\d+)\]', line)
    if m:
        gh_to_task[int(m.group(2))] = m.group(1)
```

### 6. Create dependency links

```python
for blocker, blocked_list in deps.items():
    for blocked in blocked_list:
        subprocess.run([
            "hermes", "kanban", "--board", "shop", "link",
            gh_to_task[blocker], gh_to_task[blocked]
        ])
```

### 7. Create recette branch parent tasks

One meta-task per phase as merge target:

```python
for phase in ["phase-0", "phase-1", ...]:
    subprocess.run([
        "hermes", "kanban", "--board", "shop", "create",
        f"RECETTE: Phase {n} — merge target"
    ])
```

## Pitfalls

- **Don't skip the INDEX.** Creating tickets without reading the master issue means missing dependency hotspots and dispatch rules.
- **Semantic IDs, not GitHub numbers.** The `Blocks:` fields use `P1.1.1` format, never `#106`. Must map through titles.
- **Duplicate links are harmless.** Some issues list the same dependency in both `Blocks:` and body text. `hermes kanban link` is idempotent.
- **Recette tasks are meta, not blockers.** They group tasks visually but don't enforce ordering — the real blocking comes from issue-to-issue `Blocks:` dependencies.
