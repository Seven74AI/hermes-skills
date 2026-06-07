# Postpone a Blocked Task to the End of a Chain

When a task is blocked on an external dependency (expired cookies, missing credential, etc.) and it's the **head** of a sequential chain, everything downstream is stuck. If the downstream tasks can proceed independently, reorder the chain so the blocked task runs last.

## Sequence

Given a chain `T_blocked → T_2 → T_3 → T_4` where T_blocked is stuck:

```bash
# 1. Unblock the stuck task
hermes kanban --board <board> unblock <T_blocked>

# 2. Unlink it as parent of the first child (T_2 becomes parentless → auto-promotes to ready)
hermes kanban --board <board> unlink <T_blocked> <T_2>

# 3. Link the last child as new parent of the formerly-blocked task
hermes kanban --board <board> link <T_last> <T_blocked>
```

Result: `T_2 → T_3 → T_4 → T_blocked` — everything except the blocked task runs immediately.

## Multi-parent awareness

If the blocked task already has a **done** parent from the original planner chain (common in batch pipelines), linking a new parent makes it an *additional* parent. The task promotes only when ALL parents are done. A done parent is harmless — it doesn't gate.

```bash
# T_blocked has done parent t_planner, we add t_last as second parent
hermes kanban --board default show t_blocked
# parents: t_planner (done), t_last (todo)
# → promotes when t_last completes — t_planner already done, no blocking effect
```

If the existing parent is NOT done, evaluate: should the blocked task wait for it? If yes, leave it. If no, unlink the old parent too.

## Real case (2026-06-06)

Default board: `t_9859d5f8` (YouTube, blocked on expired cookies) was head of chain `t_9859d5f8 → t_f62f5ae3 → t_bcb18dcf → t_6f8025ee`. Three IG batches were stuck doing nothing. Reordered to `t_f62f5ae3 → t_bcb18dcf → t_6f8025ee → t_9859d5f8`. IG batches started immediately; YouTube waits for cookie refresh.
