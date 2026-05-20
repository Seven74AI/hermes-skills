# Ideation Pipeline — Kanban Task Graph

Multi-agent brainstorming pipeline for generating and selecting project ideas. Used when the user wants N concrete project proposals across diverse domains.

## When to use

- "Brainstorm 5 project ideas for a service that helps people"
- "Generate product ideas for domain X"
- "We need creative proposals for Y"
- Any open-ended ideation with parallel research + synthesis

## Task Graph

```
T1 (planner)
  → Defines evaluation criteria, domain categories, proposal template
  → Does NOT generate ideas — prepares the framework only

T2a (researcher)   ∥
T2b (researcher-2) ∥  All depend on T1, run in parallel
T2c (researcher-3) ∥  Each picks 2-3 domains, produces 2-3 ideas each
  ... (clone N researchers as needed for target idea count)
  → Each reads T1's output, selects domains, fills the template

T3 (reviewer)
  → Depends on ALL T2 tasks
  → Reads all proposals, evaluates against T1's criteria
  → Selects the top N ideas, polishes presentation
  → Adds personal recommendation
```

## Profile scaling

Default setup: 1 `planner`, 1 `researcher`, 1 `reviewer`.

For 3 parallel research tracks → clone 2 extra researchers:
```bash
hermes profile create researcher-2 --clone-from researcher
hermes profile create researcher-3 --clone-from researcher
```

Formula: `researchers_needed = ceil(target_ideas / 2)`. Each researcher produces 2-3 ideas.

## T1 body template (planner)

Focus: framework, not ideas. Tell the planner explicitly NOT to generate ideas.

Key elements in the body:
- Mission statement
- Required outputs: evaluation grid (5-7 criteria), domain categories (8-10), proposal template
- Format: markdown, structured for researcher consumption
- Constraint: "Do NOT generate ideas — prepare the framework only"

## T2 body template (researcher)

Focus: "read T1's output, then generate." 

Key elements:
- Tell them to read T1 first
- Coordinate domain selection with peers (check comments)
- Produce 2-3 ideas per researcher, following T1's template
- Include self-evaluation against T1's criteria

## T3 body template (reviewer)

Focus: selection + polish.

Key elements:
- Read ALL T2 outputs
- Evaluate against T1 criteria
- Select top N (user's target count)
- Explain rejections briefly
- Polish presentation to founder-ready format
- Add personal top pick recommendation

## CLI commands (reference)

```bash
# Create board
hermes kanban boards create <project-name>

# Create tasks (note: --board before create, title as positional arg)
hermes kanban --board <board> create --assignee planner \
  --body "$(cat body.md)" --tenant <tenant> --priority 10 'T1: title'

# Link dependencies via --parent (repeatable)
hermes kanban --board <board> create --assignee researcher \
  --parent <t1_id> --body "$(cat body.md)" --tenant <tenant> 'T2a: title'

# Combined T3 with multiple parents
hermes kanban --board <board> create --assignee reviewer \
  --parent <t2a_id> --parent <t2b_id> --parent <t2c_id> \
  --body "$(cat body.md)" --tenant <tenant> 'T3: title'
```

## Worker coordination: domain selection via comments

When N parallel researchers share a resource pool (domain list from T1), they risk picking the same domains and producing redundant ideas. The pattern to avoid this:

1. **First researcher to start posts a comment** declaring which domains they're taking, e.g.: *"Je prends #1 Santé mentale, #3 Inclusion, #5 Lien social. T2b/T2c : les 7 autres sont à vous."*
2. **Other researchers read this comment before picking domains** and choose from the remaining pool.
3. **Each researcher re-posts their domain picks as a comment** so there's a full audit trail.
4. **Instruct this in the T2 body:** *"Coordonne-toi avec les autres chercheurs (T2b, T2c) pour ne pas tous prendre les mêmes — lisez leurs commentaires."*

This relies on kanban comments being visible across workers (they share the same task's comment thread via parent task context).

## Pitfalls

- **Creating T2 before T1 finishes:** T2 needs T1's domains and template. Always link T2 with `--parent <t1_id>` so T2 stays in `todo` until T1 is done.
- **Name collisions across parallel workers:** Two researchers may independently pick the same project name (e.g., both name an idea \"KAIROS\"). Workers can't see each other's workspaces — they only see T1's output and task comments. Mitigation: instruct workers to prefix names with their track letter (T2a-Name, T2b-Name) OR the reviewer (T3) handles dedup as part of synthesis. The reviewer should be instructed to flag and resolve name collisions.
- **Not telling T1 to stop at the framework:** A planner without explicit "don't generate ideas" will often do the researchers' work, defeating parallelization.
- **Not cloning enough researchers:** 1 researcher × 5 ideas is serial. Clone to 2 researchers max (hard cap) for 2× speedup.
- **T3 created without parent links:** If T3 starts before T2 finishes, it has nothing to review. Always chain T3 with `--parent` for every T2 task.
- **Forgetting to switch --board:** All commands need `--board <name>`. The default board is NOT the project board.
