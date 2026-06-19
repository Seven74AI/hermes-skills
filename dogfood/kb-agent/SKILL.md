---
name: kb-agent
description: "KB Agent project — custom Python agent replacing Hermes KB pipeline. Code, vault, kanban, Edgee toggle, infrastructure isolation."
version: 1.0.0
metadata:
  hermes:
    tags: [kb-agent, project, knowledge-base, agent, reference]
---

# KB Agent — Project Configuration

Custom Python agent replacing Hermes KB pipeline layers A (ingestion), B (orchestration), D (synthesis). Load this skill when working on the KB Agent codebase or discussing its architecture.

Also load `edgee-setup` for LLM gateway configuration — Edgee is the optional gateway, DeepSeek direct is the default.

## Repos

| Repo | URL | Purpose |
|------|-----|---------|
| `Seven74AI/kb-agent` | `github.com/Seven74AI/kb-agent` | Agent source code |
| `Seven74AI/kb-agent-obsidian-vault` | `github.com/Seven74AI/kb-agent-obsidian-vault` | Notes produced by KB Agent |

Both **private**.

- Code working directory: `/root/kb-agent/`
- Vault path: `/root/kb-agent-vault/`
- Git credential helper: `git config credential.helper '!gh auth git-credential'` (set in both repos)

## Kanban

- **Board:** `kb-agent`
- **Assignees:** `coder` (implementation), `reviewer` (auto-swarm)
- **Pattern:** Swarm v1 — coder → reviewer → auto-unblock. Tickets chained with `--parent`.
- **Ticket count:** 9 tickets, phased 0-6
- **Current status:** `hermes kanban --board kb-agent list`

## Tech Stack

- Python 3.11+, Flask, sqlite3 (stdlib), httpx, asyncio, PyYAML
- LLM: DeepSeek v4 Pro (OpenAI-compatible `/v1/chat/completions`)
- Optional: Edgee gateway (`https://api.edgee.ai/v1/chat/completions`) — toggle via `config.yaml: llm_provider`
- Canonical scripts: Symlinked from `/root/.hermes/skills/productivity/knowledge-base/scripts/`
- Templates: Copied from knowledge-base skill
- No agent frameworks (no LangChain, CrewAI, etc.)
- No timeouts anywhere (HTTP calls only: ~30s built-in)

## LLM — Edgee Toggle

Both DeepSeek and Edgee use identical OpenAI-compatible format. Toggle is a one-line `config.yaml` change:

```python
# DeepSeek direct (default)
base_url = "https://api.deepseek.com/v1"

# Edgee (add compression_model for compression)
base_url = "https://api.edgee.ai/v1"
extra_fields = {"compression_model": "claude"}
```

See `edgee-setup` skill for full API reference, SDK usage, and compression metrics.

## Infrastructure Isolation

KB Agent and Hermes KB pipeline run on the same VPS but fully isolated:

| Resource | Hermes | KB Agent |
|----------|--------|----------|
| MinIO bucket | `knowledge-base/` | `kb-agent-archive/` |
| Obsidian vault | `OBSIDIAN_VAULT_PATH` | `/root/kb-agent-vault/` |
| Cookies | `/root/.hermes/cookies/` | `/root/kb-agent/cookies/` |
| Config | `~/.hermes/` | `/root/kb-agent/` |
| Firecrawl | `localhost:3002` (shared, stateless) | Same |

## Architecture

Single Python process — Flask (sync, main thread) + asyncio consumer (background thread). SQLite ×2: `agent.db` (tasks + steps) and `logs.db` (step output + LLM archives). FTS5 search on both.

Detection → dedup → pre-flight health → task creation → consumer claims → mechanical steps → LLM synthesis → quality gates → See Also → MinIO upload → Git push.

No timeouts. Streaming progress via `readline()` to logs.db. Hang detection via dashboard staleness.

## Key Docs

- `/root/kb-agent/CONTEXT.md` — Architecture, glossary, all decisions
- `/root/kb-agent/.hermes/plans/2026-06-19_000000-kb-agent-v1.md` — Full implementation plan (28 tasks)
- Edgee API reference: `edgee-setup` skill → `references/edgee-api-reference.md`

## Templates & Scripts

Templates copied from knowledge-base skill (identical format for A/B comparison):
- `templates/book-note-template.md`
- `templates/youtube-note-template.md`
- `templates/resume-prompt.md`

Canonical scripts symlinked:
- `scripts/diarize.py` → `/root/.hermes/skills/productivity/knowledge-base/scripts/diarize.py`
- `scripts/transcribe.py` → `/root/.hermes/skills/productivity/knowledge-base/scripts/transcribe.py`

## No Hermes Carryover

May 2026 Edgee streaming bugs were Hermes-specific (HTTP/2, h11, agent loop). KB Agent calls Edgee directly via httpx — standard OpenAI-compatible endpoint. Both streaming and non-streaming supported per Edgee SDK docs. Do NOT carry Hermes conclusions to KB Agent — clean slate.
