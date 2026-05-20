# Ops Re-Audit Pattern

When infrastructure evolves (profile cleanup, disk purge, kanban refactor), old ops tickets recommending actions become stale. Rather than guessing which recommendations still apply, run a structured re-audit.

## When to run

- After major infra changes (profile simplification, disk cleanup, max_spawn tuning)
- When the user asks "did we actually apply all those audit recommendations?"
- When ops tickets are more than a few days old and infrastructure has changed

## Pattern

1. Create a **researcher** ticket on the ops board
2. Task reads ALL old ops tickets, cross-checks against current system state
3. Tags each as: **KEEP** (still relevant, not done), **PARTIAL** (partially done), **OBSOLETE** (problem gone / profile deleted / pipeline dismantled)
4. Outputs a synthesis table + top actionable items

## Example prompt

```
Re-audit all hermes-ops tickets against current system state.
For each ticket: check if problem still exists, if recommendation still applies, if it's already fixed another way.
Tag each: KEEP / PARTIAL / OBSOLETE.
Produce synthesis table + top 3 immediate actions with exact commands.
```

## Current state snapshot (gather before analysis)

```bash
echo "=== DISK ===" && df -h / && echo "=== RAM ===" && free -h && echo "=== PROFILES ===" && hermes profile list && echo "=== CRON ===" && hermes cron list
```

## What to check per ticket

| Ticket type | Check |
|-------------|-------|
| RAM/CPU audit | `free -h`, `ps aux | grep mcp-google`, `systemctl status hermes-gateway` |
| Disk audit | `df -h`, `du -sh /root/.hermes/kanban/boards/*/workspaces/` |
| Profile audit | `hermes profile list`, check for deleted profiles referenced by tasks |
| Cron/watchdog | `hermes cron list`, check for deployed watchdog scripts |
| Feature analysis | Was the feature a proposal or an implementation? If proposal & never coded → PARTIAL |
| Crash/bug fix | Is the affected component still running? If profile/board deleted → OBSOLETE |

## Synthesis format

| Ticket | Title | Verdict | Action remaining |
|--------|-------|---------|------------------|
| t_xxx | ... | KEEP / PARTIAL / OBSOLETE | Exact command or "none" |

## After re-audit

For each KEEP and actionable PARTIAL: create a new task with the exact remaining command.
For OBSOLETE: no action.
