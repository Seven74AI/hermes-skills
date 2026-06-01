# OOM Diagnosis — Worked Example (2026-05-31)

## Symptoms
- Gateway restarts automatically with no user command
- User receives "⚠️ Gateway shutting down" in-chat
- `systemctl show hermes-gateway` shows `MemoryPeak=11.2G`, `MemorySwapPeak=7.9G`

## Root Cause
15 concurrent kanban coder workers spawned after a large audit decomposition
(the-swarm dispatch spawned 12 tasks: 9 coders + 2 researchers + 1 planner,
plus existing workers from shop and music-library). Each coder runs:
- vitest (200-400MB)
- playwright + chrome-headless (300-800MB each)
- npm install / esbuild (100-300MB)
- Total per coder: 500MB-1GB

Result: 15 × ~700MB = ~10.5GB, exceeding the VPS's 11GB total RAM.

## Detection Commands

```bash
# OOM kill log
dmesg -T | grep -i "oom.*killed" | tail -5
# [Sun May 31 09:54:25 2026] Out of memory: Killed process 1337455 (node) total-vm:2571736kB
# [Sun May 31 10:05:42 2026] Out of memory: Killed process 1373201 (chrome-headless) total-vm:1518233268kB

# Memory at crash
journalctl -u hermes-gateway --since "1 hour ago" --no-pager | grep "memory peak"
# → Consumed 10.7G memory peak, 7.4G memory swap peak

# Count orphaned worker processes
ps aux | grep 'kanban/boards/.*workspaces' | grep -v grep | wc -l
```

## Fix Applied
Reduced `delegation.max_concurrent_children` from 7 to 5 on the coder profile:
```bash
hermes config set --profile coder delegation.max_concurrent_children 5
```

## Post-Fix Health
```bash
systemctl show hermes-gateway | grep -E "Memory(Swap)?(Current|Peak)"
# MemoryCurrent=7469309952 (~7GB)
# MemorySwapCurrent=450588672 (~450MB)
```
Swap dropped from 3.3GB → 450MB. No further OOM events.
