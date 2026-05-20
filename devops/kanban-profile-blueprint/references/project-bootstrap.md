# Project Bootstrap Flow

End-to-end recipe for creating a new kanban project from zero to autonomous.

## When to use

Creating a new game, app, library, or any workstream that needs its own board + repo + skill.

## Prerequisites

- Generic profiles exist: `coder`, `reviewer`, `researcher`, `planner`
- GITHUB_TOKEN in `~/.hermes/.env`
- Godot installed at `/usr/local/bin/godot4` (for game projects)

## Flow

### 1. Create GitHub repo

```bash
gh repo create Seven74AI/<slug> --public -d "<description>"
```

No fork upstream needed — create fresh on Seven74AI.

### 2. Create kanban board

```bash
hermes kanban boards create <slug>
```

Board name = repo slug. Display name auto-generated (Title Case).

### 3. Create project skill

```bash
# Copy structure from an existing project skill (videogame-lab)
# Must include: GitHub, Kanban, Profiles, Tech Stack, Testing, Pipeline sections
```

Category: `dogfood`. Name: `<slug>`. Keep it lean — concept section for game direction, but don't over-specify.

### 3b. CRITICAL: Sync skill to ALL worker profiles

Skills are **per-profile**. `skill_manage()` creates only in the main `~/.hermes/skills/`. Worker profiles have their own copy at `~/.hermes/profiles/<name>/skills/`. If you skip this step, ALL workers on the new project will crash with "Unknown skill(s): <slug>" — repeatedly, and the crash pattern will be identical to an API issue, misleading diagnosis.

```bash
for p in coder reviewer researcher planner; do
  mkdir -p ~/.hermes/profiles/${p}/skills/dogfood/<slug>
  cp ~/.hermes/skills/dogfood/<slug>/SKILL.md ~/.hermes/profiles/${p}/skills/dogfood/<slug>/SKILL.md
done

# Verify
for p in coder reviewer researcher planner; do
  hermes -p "$p" --skill <slug> chat -q "say ok" 2>&1 | grep -q "Duration:" && echo "✓ $p" || echo "✗ $p FAILED"
done
```

**Historical note**: Skipping this step caused 8 researchers across baguette+glance boards to crash 5+ times each before root cause was found (2026-05-19). The crash pattern (all exit_code 1, all ~60s) mimicked an API issue, leading to a false config change (max_spawn 5→3). Always sync skills.

### 4. Initialize git workspace

```bash
TOKEN=$(grep '^GITHUB_TOKEN=' ~/.hermes/.env | head -1 | cut -d= -f2-)
mkdir -p /tmp/<slug>
cd /tmp/<slug>
git init
git remote add origin "https://git:${TOKEN}@github.com/Seven74AI/<slug>.git"
git branch -m master main
git config --unset credential.helper 2>/dev/null
```

Token-in-URL so workers can push without env_passthrough.

### 5. Create initial tickets with dependency chain

Standard pipeline for a new project:

```
Research tasks (4×, parallel) → Plan task (waits for all research) → Proto coder (waits for plan)
```

```bash
# Research tasks — created ready with assignee, dispatched immediately
hermes kanban --board <slug> create "RESEARCH: Concept & narrative" --assignee researcher --skill <slug>
hermes kanban --board <slug> create "RESEARCH: Game design" --assignee researcher --skill <slug>
hermes kanban --board <slug> create "RESEARCH: Bestiary/enemies" --assignee researcher --skill <slug>
hermes kanban --board <slug> create "RESEARCH: Technical feasibility" --assignee researcher --skill <slug>

# Plan task — depends on all research (created after research IDs known)
hermes kanban --board <slug> create "PLAN: Roadmap" --assignee planner --skill <slug> \
  --parent <research_id_1> --parent <research_id_2> --parent <research_id_3> --parent <research_id_4>

# Proto task — depends on plan + all research
hermes kanban --board <slug> create "PROTO: Core loop" --assignee coder --skill <slug> \
  --parent <research_id_1> --parent <research_id_2> --parent <research_id_3> --parent <research_id_4>

# Link plan as parent of proto
hermes kanban --board <slug> link <plan_id> <proto_id>
```

Research tasks dispatch immediately (ready + assignee). Plan and proto stay `todo` until all parents complete.

### 6. Verify

```bash
hermes kanban --board <slug> list
```

Should show: 4 ready research, 1 todo plan, 1 todo proto.

### 7. Dispatch takes over

Dispatcher runs every 60s in the gateway (`dispatch_interval_seconds: 60`). Research tasks picked up within a minute.

## Anti-patterns

- **Creating tickets without parent-child links** — research and plan run in parallel, plan has no context, proto starts before research done.
- **Forgetting git auth** — first coder can't push, task blocks on review with no code on GitHub.
- **Not loading the blueprint skill** during setup — reinventing the flow from memory instead of following this document.
- **Skipping step 3b (skill sync)** — workers crash repeatedly with "Unknown skill." The crash pattern mimics API issues and leads to false diagnosis.

## Cross-reference

- Git auth: see main SKILL.md § "Git authentication"
- Profile verification: see main SKILL.md § "Post-Deployment Verification"
