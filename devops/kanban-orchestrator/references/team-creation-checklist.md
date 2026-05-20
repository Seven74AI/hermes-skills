# Team Creation Checklist — Spin Up a New AI Agent Team

Repeatable recipe for creating a new specialist AI agent team with full infrastructure. Used for videogame-lab (8 profiles) and edgee-lab (6 profiles).

## Step 1 — Design the roster

Pick roles based on the team's mission. Standard pattern: planner, researcher(s), coder/implementer, reviewer. Adapt to domain:
- **Game dev**: planner, designer, coder, 3d-artist, 2d-artist, sound-designer, writer, reviewer
- **Research/infra**: planner, researcher (×2), integrator, watcher, reporter

Scale decision: 1 of each initially, clone on demand when parallelism is needed.

## Step 2 — Create profiles

```bash
hermes profile create <team>-planner --clone-from default
hermes profile create <team>-researcher --clone-from default
hermes profile create <team>-coder --clone-from default
hermes profile create <team>-reviewer --clone-from default
# etc.
```

All profiles inherit `default`'s config, model, and API keys from shell env.

## Step 3 — Write SOUL.md for each profile

Each SOUL.md at `~/.hermes/profiles/<name>/SOUL.md`. Format:

```markdown
# Hermes Agent Persona

You are a <ROLE TITLE>. <One-line mission statement>.

RULES:
- <Domain-specific rule 1>
- <Domain-specific rule 2>
- ...
```

Key principles:
- **Role-specific, not generic.** A game-coder SOUL.md mentions 60fps targets and mobile GPU budgets. A shop-coder SOUL.md mentions Express 5 wildcards and Prisma v7.
- **Include domain constraints.** Target platforms, performance budgets, tool preferences, file format standards.
- **Include handoff patterns.** How to complete/block tasks, what metadata to include, what format downstream workers expect.
- **English only.** Even if the user speaks French, all SOUL.md and team communication is in English (user preference).
- **Keep it concise.** 15-25 lines. The worker's system prompt is already large — SOUL.md is the focused specialization layer.

## Step 4 — Create infrastructure

```bash
# Kanban board (task orchestration)
hermes kanban boards create <team-name>

# GitHub repo
gh repo create Seven74AI/<team-name> --public \
  --description "<one-line mission>"

# Notion page (under root page from memory)
source ~/.hermes/.env
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"parent": {"page_id": "<root_page_id>"},
       "properties": {"title": {"title": [{"text": {"content": "<Team Name>"}}]}},
       "markdown": "# <Team Name>\n\n<mission>\n\n## Team\n\n- list profiles\n\n## Links\n\n- GitHub: ..."}'
```

## Step 5 — Decompose into tasks

Follow the standard orchestration pattern (see ideation-pipeline.md for multi-researcher fan-out):

```bash
# T1: Planner decomposes the mission (does NOT execute)
hermes kanban --board <team> create \
  --assignee <team>-planner --tenant <team> --priority 10 \
  --body '<decomposition prompt>' 'T1: Define plan'

# T2a, T2b, T2c: Parallel workers, gated on T1
hermes kanban --board <team> create \
  --assignee <team>-researcher --parent <t1_id> \
  --tenant <team> --body '...' 'T2a: ...'

# T3: Synthesis/review, gated on all T2s
hermes kanban --board <team> create \
  --assignee <team>-reviewer --parent <t2a_id> --parent <t2b_id> \
  --tenant <team> --body '...' 'T3: ...'
```

## Step 6 — Set up recurring jobs

For teams that need ongoing monitoring or reporting:

```bash
# Daily report cron (if the team has a reporter role)
hermes cron create \
  --name "<Team> Daily Report" \
  --schedule "0 9 * * *" \
  --prompt "<self-contained report compilation prompt>" \
  --deliver "discord:<channel>" \
  --skills xurl,blogwatcher \
  --model deepseek-v4-pro
```

## Step 7 — Verify

```bash
hermes kanban --board <team> list --tenant <team>
hermes profile list | grep <team>
```

At least T1 should show `running` (picked up by dispatcher). Dependent tasks show `todo` until their parents complete.

## Pitfalls

- **Forgetting --tenant on task creation.** Every `kanban create` needs `--tenant <team>` or tasks land in the default tenant and won't show up on the board.
- **Forgetting --board on kanban commands.** Default board is NOT the project board. Always pass `--board <team>`.
- **Not writing SOUL.md.** Profiles cloned from `default` have the generic persona. Without role-specific SOUL.md, they won't know their domain constraints.
- **Gateway must be running.** The built-in dispatcher in the gateway picks up tasks. If no gateway is running, tasks sit in `ready` forever.
- **Memory limit.** Each new team adds ~300 chars to memory. Compact existing entries when near the 2,200 char limit.
