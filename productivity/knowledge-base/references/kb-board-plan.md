# Knowledge Base Board — Setup Plan

Dedicated kanban board `knowledge-base` for all KB content processing.

## Board identity

- **Slug:** `knowledge-base`
- **DB path:** `/root/.hermes/kanban/boards/knowledge-base/kanban.db`
- **Created:** 2026-06-09
- **CONTEXT:** `/root/.hermes/kb-board/CONTEXT.md`

## Profiles

| Role | Profile | When |
|------|---------|------|
| Text/image extraction | `researcher` | Threads text, carousels, articles, books |
| Video extraction | `researcher-videos` | YouTube, Instagram Reels, Threads video |

No `kb-reviewer` needed — pipeline is 1 ticket, direct push, no PR.

## Pipeline

```
User sends URLs/books on Telegram
  → Agent creates ticket(s) on knowledge-base board
  → Worker extracts → transcribes → writes note → MinIO upload → Git push
  → Done
```

Single ticket per batch. No reviewer, no PR gate.

## Batch rules

- 5 URLs per ticket max
- Chain with `--parent` for sequential processing
- `--max-runtime 3600`
- 2 video transcriptions per worker session
- Prefix ticket title with `KB:`

## Boundaries

- `knowledge-base` board: ALL KB content only
- `default` board: sandbox for one-shots, tests, infra — NEVER KB
- `hermes-ops` board: ops tasks (MCP design, backups, watchdogs)
- GitHub Issues on `obsidian-vault`: discussion, tracking, long-lived specs

## Trigger flow

```
User → Telegram message with URLs
  → Agent detects content type (text vs video)
  → Agent creates ticket on knowledge-base board
  → Dispatcher spawns worker (researcher or researcher-videos)
```

No GitHub Issues → Kanban trigger needed; user always goes through Telegram.
