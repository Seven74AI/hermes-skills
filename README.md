# Hermes Skills

Custom skills created by the Hermes Agent for the Seven74AI infrastructure.

## Structure

Each directory contains a complete skill:
- `SKILL.md` — skill definition (YAML frontmatter + markdown body)
- `references/` — linked reference documents
- `templates/` — reusable templates
- `scripts/` — executable scripts

## Lifecycle

Skills are managed via the [hermes-skills kanban board](#) with states: **created → review → published → stale → archived**

## Sync

Auto-synced from `~/.hermes/skills/` on creation/modification via cron job.
