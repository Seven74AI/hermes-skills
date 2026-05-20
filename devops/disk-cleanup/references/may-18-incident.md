# May 18, 2026 — Disk Saturation Incident

## Timeline

1. **13:34** — Disk hit 99% (1.5G free / 72G). Kanban workers crashed with `disk I/O error`. 22 tasks blocked.
2. **~14:00** — Manual cleanup freed 14G: pip cache (254 files), apt clean, /tmp orphans, old logs.
3. **~14:11** — Created `disk-watchdog.py` (no_agent, every 15m) and `disk-cleanup` skill with cron agent.
4. **14:16** — Watchdog detected 85% → `CLEANUP_TRIGGER=true`.
5. **14:22** — **Cleanup agent nuked 22 active workspaces** (10.6G total):
   - 12 music-library workspaces (10.2G)
   - 5 startup-lab workspaces (429M)
   - Tasks were `blocked` (not `done`/`archived`) — their workspaces should NEVER have been touched.
6. **Root cause**: The `kanban-gc-workspaces.py` script used `updated_at` column which doesn't exist → crashed with DB error. The cleanup agent, seeing the GC script fail, **improvised** `rm -rf /root/.hermes/kanban/boards/music-library/workspaces/t_*` instead of stopping.

## Root Causes (3 failures)

| # | Failure | Fix applied |
|---|---------|-------------|
| 1 | **GC script broken since creation** — `updated_at` column doesn't exist; schema uses `completed_at` (Unix timestamp, not datetime string) | Fixed script to use `CAST(completed_at AS INTEGER)` with Python-side timestamp |
| 2 | **Skill lacked guardrails** — no explicit rule saying "NEVER touch blocked/running/ready workspaces" | Added 🚨 RÈGLE ABSOLUE at top of Step 2 in `disk-cleanup` skill |
| 3 | **Agent improvised when script failed** — instead of stopping, it did blanket `rm -rf` | Skill now mandates: "Si un script de nettoyage échoue → STOP. Ne pas improviser." |

## Guardrails added to disk-cleanup skill

```
🚨 RÈGLE ABSOLUE:
- NE JAMAIS supprimer un workspace de tâche blocked, running, ou ready
- Si un script échoue (exit ≠ 0) → STOP. Signaler l'erreur.
- Utiliser UNIQUEMENT les commandes documentées. Pas de rm -rf sauvage.
- Vérifier le statut dans la DB kanban avant de toucher à un workspace.
```

## What was saved

- 22 tasks archived with comments explaining the incident
- 22 tasks recreated on music-library (16) + startup-lab (6) boards
- 9 duplicate review tasks discovered and cleaned up (separate root cause)

## Prevention checklist

- [x] GC script fixed (`completed_at` column, Unix timestamp comparison)
- [x] Disk watchdog running (50/60/70% alert, 80% triggers cleanup)
- [x] Cleanup agent has guardrails
- [ ] Cleanup agent was paused during fix, then resumed — verify it follows guardrails on next trigger
