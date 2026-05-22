---
name: kanban-profile-blueprint
description: Blueprint for creating and maintaining Hermes kanban worker profiles — config templates, role definitions, bootstrap script, and all lessons learned from production firefighting.
version: 1.11.0
platforms: [linux]
metadata:
  hermes:
    tags: [kanban, profiles, devops, workflow, template]
---

# Kanban Profile Blueprint

Blueprint for kanban worker profiles. Covers role definitions, config templates,
and all systemic fixes discovered during production operations.

## Profiles we actually need (simplified)

Instead of 24+ profiles per project, use **role-based profiles** with
project-specific SOUL.md. The same coder works on any board.

| Role | Profile | Needs git push? | max_turns | Notes |
|------|---------|----------------|-----------|-------|
| Coder | `coder` | Yes | 90 | Implements code + tests. Background+wait = ~15-20 turns. |
| Reviewer | `reviewer` | No (GitHub App) | 90 | Reviews PRs/diffs. Approves via GitHub App. |
| Researcher | `researcher` | Maybe | 90 | Investigates, writes docs. |
| Planner | `planner` | No | 90 | Decomposes into tasks. Never implements. |

**No `coder-long` needed.** Background+wait + self-contained scripts make 90 turns
sufficient for any task.

## Playwright E2E sharding (standard)

All projects use **2-shard matrix + gate job** for E2E tests. Branch protection
context MUST be `playwright-gate` (NOT `playwright` — matrix creates suffixed names).

See `references/ci-context-matching.md` for full recipe including emoji name fix
and gate job YAML template.

## Branch Protection Context Matching

Required status checks MUST match **exact** CI job names. Emoji `name:` fields and
matrix suffixes break auto-merge. See `references/ci-context-matching.md` for
diagnosis and fixes.

## Common pitfalls & fixes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `|| true` or `--if-present` on CI typecheck/lint | Silently swallows errors | Remove the flag. See `references/ci-gate-pitfalls.md`. |
| Auto-merge stuck "waiting for status to be reported" | Emoji names or matrix suffixes mismatch required contexts | Remove `name:` fields + gate job for matrix. See `references/ci-context-matching.md`. |
| Ghost PRs accumulate on upstream | Workers create PRs never merged | Close + delete fork branches. See `references/ghost-pr-cleanup.md`. |
| Coder merges upstream but never fork main | Fork main gap | Merge to fork main first. See `references/fork-main-merge-gap.md`. |
| Worker exhausts budget on test output | Inline tests burn iterations | `test:all` script + background+wait. See `references/test-all-script-pattern.md`. |

## Key references

- `references/ci-context-matching.md` — Emoji names, matrix sharding, gate job pattern
- `references/ci-gate-pitfalls.md` — `|| true`, `--if-present` in CI
- `references/ghost-pr-cleanup.md` — Cleanup stale worker PRs
- `references/fork-main-merge-gap.md` — Fork divergence recovery
- `references/align-existing-project.md` — Bring project to shop-level standards
- `references/project-bootstrap.md` — New project setup
- `references/test-all-script-pattern.md` — `test:all` for token economy
- `references/operational-infrastructure.md` — Cron jobs, watchdogs, GC
- `references/skill-sync-crash-diagnosis.md` — "Unknown skill" crashes

## Bootstrap script

Single command to create all profiles:

```bash
for profile in coder reviewer researcher planner; do
  hermes profile create "$profile" --clone 2>/dev/null || echo "$profile exists"
  python3 -c "
import yaml
path = '/root/.hermes/profiles/$profile/config.yaml'
with open(path) as f: cfg = yaml.safe_load(f)
cfg['model'] = {'default': 'deepseek-v4-pro', 'provider': 'deepseek', 'base_url': 'https://api.deepseek.com/v1'}
cfg.pop('provider', None)
with open(path, 'w') as f: yaml.dump(cfg, f, default_flow_style=False)
"
done
```
