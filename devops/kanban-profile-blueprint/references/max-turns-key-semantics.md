# Hermes Agent Iteration Budget: Key Semantics

Traced through the codebase 2026-07-01. One session of config surgery
across 4 profiles. This documents what each key ACTUALLY does, to prevent
future agents from checking dead keys or misunderstanding the hierarchy.

> ⚠️ **Contradiction to watch for:** `kanban-project-workflow`'s "Worker Tuning → max_iterations vs max_turns" section still claims **root-level `max_turns`** is the governing key. That is WRONG per this trace — `agent.max_turns` governs, and root-level `max_turns` is a dead legacy fallback. This stale claim misled a SOUL-harmonization pass (2026-08-20) into treating a dead root-level `max_turns: 120` as active. As of 2026-08-20 that skill's SKILL.md also exceeds the 100 KB patch limit (100,223 chars), so it can't be corrected in place — treat its Worker Tuning section as stale and trust this doc.

## The only key that matters: `agent.max_turns`

```yaml
agent:
  max_turns: 180   # ← THIS is the iteration budget. Default: 90.
```

### How it flows

1. **CLI path** (`cli.py:2967-2980`): `CLI_CONFIG["agent"]["max_turns"]` → `self.max_turns` → `AIAgent(max_iterations=self.max_turns)`

2. **Gateway path** (`gateway/run.py:705-707`): `agent.max_turns` from config.yaml → bridged to `HERMES_MAX_ITERATIONS` env var at startup. Also re-bridged on every `.env` reload (`_reload_runtime_env_preserving_config_authority`).

3. **Setup path** (`setup.py:1815`): When user changes max iterations, it writes to `agent.max_turns` (and strips stale `HERMES_MAX_ITERATIONS` from `.env`).

### Resolution priority (CLI)

```
CLI arg (--max-turns) > agent.max_turns > root max_turns (legacy) > HERMES_MAX_ITERATIONS env > default 90
```

## Dead keys (NEVER consumed)

| Key | Location | Why dead |
|-----|----------|----------|
| `max_turns` | **root level** | Legacy. Normalization in `_load_config_impl` (config.py:4432-4437) and `_normalize_max_turns_config` (config.py:4268-4281) migrates root→agent ONLY if `agent.max_turns` is missing. Then strips the root key. `save_config` also strips it. |
| `max_iterations` | **root level** | Never consumed by any code path. No normalization exists for it. |
| `agent.max_iterations` | under `agent:` | Never read by `cfg_get`, `CLI_CONFIG`, or `_load_config_impl`. The `AIAgent.__init__` parameter is named `max_iterations` but it receives its value from `agent.max_turns`, not from `agent.max_iterations`. |

## Keys that DO something (but are different subsystems)

| Key | Default | What it controls |
|-----|---------|-----------------|
| `agent.max_turns` | 90 | Agent iteration budget (main loop tool-calling turns) |
| `goals.max_turns` | 20 | Goal-mode auto-pause: max continuation turns before `/goal resume` required in gateway |
| `delegation.max_iterations` | 45 (CLI default) / 50 (config default) | Per-subagent iteration cap; independent of parent's `agent.max_turns` |
| `kanban.max_iterations` | 120 (per audit) | Kanban dispatcher iteration budget (different subsystem, NOT related to agent loop) |

## Profile-specific values (as of 2026-07-01)

| Profile | `agent.max_turns` | Rationale |
|---------|-------------------|-----------|
| coder | 180 | 2× default; complex multi-file code changes need more iterations |
| reviewer | 90 | PR review rarely needs >50 turns |
| researcher | 90 | Research tasks are usually short |
| planner | 90 | Decomposition is fast |
| edgee-planner | 90 | Default |
| twitter-coder | 90 | Default |
| hermes-devops | 90 | Default |
| researcher-videos | 240 | Long video processing pipelines |

## How to change it

```bash
hermes config set --profile <name> agent.max_turns <value>
```

This writes to config.yaml under `agent.max_turns` and strips any stale
root-level `max_turns` automatically (via `save_config` normalization).
