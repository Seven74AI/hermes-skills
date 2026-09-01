---
name: kanban-profile-blueprint
description: Blueprint for creating and maintaining Hermes kanban worker profiles — config templates, role definitions, bootstrap script, and all lessons learned from production firefighting.
version: 1.12.0
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
| Coder | `coder` | Yes | 180 | Implements code + tests. Needs 2× default for complex multi-file changes. |
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
| Worker polls with heartbeats during CPU task | SOUL.md missing `process(wait)` mandate | Add explicit background+wait section to profile SOUL. See `references/background-wait-enforcement.md`. |
| Config has root-level `max_turns` or `max_iterations` | Dead legacy key, silently ignored | Remove from config. Only `agent.max_turns` controls budget. See `references/max-turns-key-semantics.md`. |
| Reviewer task stuck in `todo` forever | SOUL.md Review Handoff missing `promote` step | Add `terminal("hermes kanban --board <board> promote <review_id>")` after `kanban_create`. `kanban_create()` creates in `todo`, dispatcher only picks up `ready`. |
| Worker calls `kanban_complete()` instead of `kanban_block()` | SOUL.md has both Review Handoff (→block) AND Completion (→complete) sections | Disambiguate: review-requiring tasks → block; non-review tasks → complete. If ALL tasks require review, remove `kanban_complete` from termination path entirely. See `references/contradiction-check.md` check #7. |
| Reviewer REJECT leaves coder blocked forever | Reviewer SOUL.md REJECT path calls `kanban_complete(approved:false)` without unblocking coder | Add `unblock <coder_id>` to REJECT before completing; route fixable failures (missing handoff, validation failed) to NEEDS CHANGES not REJECT. See `references/contradiction-check.md` checks #8/#9. |
| SOUL.md budget ≠ config `agent.max_turns` | Budget number drifted during edits | Align SOUL.md to match config. Run `references/contradiction-check.md` check #1 after every SOUL edit. Coder is 180; all other standard profiles are 90 (or higher if project-specific). |

## Key references

- `references/ci-context-matching.md` — Emoji names, matrix sharding, gate job pattern
- `references/ci-gate-pitfalls.md` — `|| true`, `--if-present` in CI
- `references/ghost-pr-cleanup.md` — Cleanup stale worker PRs
- `references/fork-main-merge-gap.md` — Fork divergence recovery
- `references/align-existing-project.md` — Bring project to shop-level standards
- `references/project-bootstrap.md` — New project setup
- `references/test-all-script-pattern.md` — `test:all` for token economy
- `references/background-wait-enforcement.md` — Mandating `process(wait)` in profile SOUL.md for CPU-bound tasks
- `references/max-turns-key-semantics.md` — Full trace of `max_turns`/`max_iterations` key semantics: what's dead, what's active, and how the config→runtime bridge works
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
