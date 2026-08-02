# Curator Workflow — Skill Library Curation Pass

Proven pattern for running a full skill library curation pass.

## Quick run (prune-only)

```bash
hermes curator run
```

This runs in prune-only mode unless `curator.consolidate: true` in config.yaml. It archives agent-created skills idle for 90+ days.

## Full pass (with consolidation)

When you want the LLM to identify near-duplicates and create umbrellas:

```bash
# 1. Survey current state
hermes curator status
hermes curator usage

# 2. Manually check candidate duplicate pairs with skill_view
# Look at pairs with similar descriptions or overlapping domains

# 3. Run consolidation (LLM merge pass)
hermes curator run --consolidate

# 4. Check for prunable skills
hermes curator prune --dry-run --days 90
hermes curator prune --days 90 -y

# 5. Verify
hermes curator status
hermes curator list-archived
```

## What the curator touches

- **Agent-created skills only** — bundled and hub-installed skills are never touched
- **Pinned skills** — skipped by automatic transitions (can still be patched manually)
- **Consolidation** — creates umbrellas, absorbs small skills, prunes stale bundled skills

## Common pitfalls

- `prune --days 90` finds nothing if all agent skills were recently active — it only checks agent-created skills, not bundled ones
- `--consolidate` must be passed explicitly when `curator.consolidate: off` in config
- After consolidation, check for stale `related_skills` references in umbrella skills — the curator may not update these
- Skills with `last_activity=never` may be bundled (shipped with Hermes, never used) — they're removed by consolidation, not prune
