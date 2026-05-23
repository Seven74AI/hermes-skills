# Cron Consolidation — Merging Overlapping Cron Jobs

## When to consolidate

Multiple cron jobs should be merged when they:
1. Analyze the **same data** (sessions, kanban state, disk) over the **same time window** (24h)
2. Produce **overlapping outputs** (70%+ shared content)
3. Run within a few hours of each other

## Anti-pattern: single monolithic job

A single job with 7+ sections dilutes focus. The model skims each section instead of going deep. Split by **mission**, not by schedule.

## Pattern: decompose by mission (final design, 2026-05-22)

### Before (4 overlapping jobs)

| Job | Time | Mission |
|-----|------|---------|
| Daily Recap | 00:00 | Human-facing activity summary → Discord |
| nightly-reflector | 01:00 | Pattern detection, skill/memory updates |
| Hermes Chronicle | 05:00 | Technical lessons → Notion (durable) |
| midday-reflector | 13:00 | Memory hygiene (condense, purge, merge) |

### Problems found

- 70% overlap between nightly and Daily Recap (kanban status, PRs, disk alerts)
- Midday reflector's core mission (memory tool) was **impossible in cron context**
- 4 deepseek-v4-pro runs/day
- Single merged job (Pass 1) had 7 sections — too diluted

### After (3 mission-focused jobs)

**Job 1 — Morning Report** (06:00, Discord, default model, `terminal`+`session_search`)

Delivers a human-readable summary. Sections: Activity, Decisions, Alerts+trends, Wins.

**Job 2 — Daily Journal** (06:05, local, `terminal`+`session_search`+`skills`+`web`)

Extracts 3-5 durable technical lessons → Notion. Self-contained, searchable in 6 months.

**Job 3 — Daily Reflection** (06:10, local, `terminal`+`session_search`+`skills`)

System improvement work. Sections: Patterns & Improvements, System Health (DB growth, backup recos), Cron Audit.

### Design principles

1. **Split by mission, not by schedule.** Report (for humans), Journal (for archive), Reflection (for the system).
2. **Stagger by 5 minutes.** Each job runs independently. If one fails, the others still deliver.
3. **Match toolsets to mission.** Report only needs terminal+session_search. Journal needs web+skills for Notion. Reflection needs skills for patches.
4. **Report uses default model** (cheaper). Journal/Reflection don't deliver to user, so cost matters less.
5. **Each job has ≤4 sections** — focused enough for deep analysis, not surface-level skimming.

## Lessons

1. **Check if the cron's mission is even possible.** Midday reflector's core job was memory hygiene via the `memory` tool — disabled in cron context.

2. **Look at actual outputs, not just prompts.** The prompts looked different but the outputs overlapped 70%.

3. **Prompt language matters.** English for instructions reduces ambiguity (French "tâches" = tasks vs stains).

4. **Use grill-with-docs for design.** Structured Q&A surfaced real needs vs assumed needs.

5. **Monolithic jobs dilute focus.** 7 sections → model skims. 3 sections → model goes deep.

6. **Consolidation checklist:**
   - [ ] Same data source? (sessions, kanban, disk)
   - [ ] Same time window? (24h)
   - [ ] Overlapping output sections? (>50% shared)
   - [ ] Can missions be clearly separated by output channel and purpose?
   - [ ] Any mission that's structurally impossible?
   - [ ] If merged → is each section short enough for deep analysis?
