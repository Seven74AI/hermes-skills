# Kanban Ticket Template for KB URL Batches

Use this template when creating tickets on the `default` board for the researcher
to process URLs into the knowledge base.

## Ticket creation command

```bash
hermes kanban --board default create \
  --assignee researcher \
  --skill knowledge-base \
  --max-runtime 3600 \
  --parent <previous_ticket_id> \
  --body "..." \
  "KB: <description> (lot X/N)"
```

## Ticket body template

For Instagram-only batches:

```
Lot X/N — N reels Instagram. Rate-limit strictly: sleep 8-15s between Reels, max 2MB/s.

1. URL — Auteur/Topic (optional annotation)
2. URL (carousel — extraire tous les slides, HARD CAP 2 slides)
3. URL
...

For Instagram: use cookies at /tmp/ig_cookies.txt. For carousel posts: extract all slides (HARD CAP 2). **CRITICAL: do NOT translate content. Note language = source language.** Save to Knowledge base/. Push after each note.
```

For mixed batches (Instagram + Threads):

```
Batch X — N URLs. Rate-limit strictly: sleep 8-15s between Reels, max 2MB/s.

N. URL — Auteur/Topic (optional annotation)
...

For Instagram: use cookies at /tmp/ig_cookies.txt. For carousel posts: extract all slides. For Threads: try web_extract or browser. CRITICAL: do NOT translate — note language = source language. Save to Knowledge base/. Push after each note.
```

## Key elements

| Element | Purpose |
|---------|---------|
| `Rate-limit strictly: sleep 8-15s` | Avoids Instagram rate-limiting / shadow-ban |
| `max 2MB/s` | Throttle yt-dlp download speed |
| `cookies at /tmp/ig_cookies.txt` | Required for Instagram authentication |
| `HARD CAP 2 slides` | Carousel anti-bot limitation — slides 3+ are blocked |
| `Keep original language` | Never translate content |
| `Knowledge base/` | Target folder in Obsidian vault |
| `Push after each note` | Git push so Obsidian syncs |
| `--parent <id>` | Chain tickets so they process sequentially |
| `--max-runtime 3600` | 1h safety net per ticket |

## Convention

- 5 URLs per ticket max
- Chain with `--parent` so each batch waits for the previous one
- Assignee: `researcher`
- Skill: `knowledge-base`
