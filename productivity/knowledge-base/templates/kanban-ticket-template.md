# Kanban Ticket Template for KB URL Batches

Use this template when creating tickets on the **`knowledge-base`** board for the researcher
to process URLs into the knowledge base.

The `default` board is a **sandbox only** — never create KB tickets there.

## Ticket creation command

**For Threads URLs:** Run Phase 0 detection FIRST (`references/pipeline-threads.md`) to determine VIDEO vs TEXT, then use the appropriate command below.

```bash
# For video content (Reels, YouTube, Threads VIDEO) — uses transcription pipeline
hermes kanban --board knowledge-base create \
  --assignee researcher-videos \
  --skill knowledge-base \
  --max-runtime 3600 \
  --parent <previous_ticket_id> \
  --body "..." \
  "KB: <description> (lot X/N)"

# For text/image content (carousels, threads, posts, articles, Substack) — no transcription needed
hermes kanban --board knowledge-base create \
  --assignee researcher \
  --skill knowledge-base \
  --max-runtime 3600 \
  --parent <previous_ticket_id> \
  --body "... Deep treatment required: Firecrawl → read ENTIRE source → Key Claims ≥4 with quotes → Section-by-section analysis (dominant) → MinIO archive (knowledge-base/articles/). Target 15K-25K chars. ..." \
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

For Instagram: use cookies at /root/.hermes/cookies/ig_cookies.txt. For carousel posts: extract all slides (HARD CAP 2). Diarization MANDATORY for ALL video. **ALWAYS run diarization and transcription with `terminal(background=true, notify_on_complete=true)` + `process(action="wait")` — NEVER inline/foreground.** See `video-pipeline-global.md` and `pipeline-instagram.md` for the exact commands. large-v3 whisper, cpu_threads=6. **Language: content in source language, labels in English.** Save to Knowledge base/. Push after each note.
```

For Substack-only batches (articles, no media detection needed):

```
Lot X/N — N articles Substack. Deep treatment required.

Firecrawl extraction → read ENTIRE source → Key Claims (≥4, with direct quotes) → Section-by-section analysis (dominant section) → Context → Critical Analysis → Nuances. Target 15K-25K chars. Upload raw markdown to MinIO (knowledge-base/articles/). Add source_files: with Tailscale FQDN.

1. URL — Publication: Title
2. URL — Publication: Title
...

Pipeline: pipeline-substack.md. Langue: contenu en langue source, labels en anglais. Save to Knowledge base/. Push après chaque note.
```

For mixed batches (Instagram + Threads):

```
Batch X — N URLs. Rate-limit strictly: sleep 8-15s between Reels, max 2MB/s.

N. URL — Auteur/Topic (optional annotation)
...

For Instagram: use cookies at /root/.hermes/cookies/ig_cookies.txt. Diarization MANDATORY for ALL video — use canonical scripts/diarize.py + scripts/transcribe.py (never skip, even for apparent monologues). **⛔ ALWAYS run diarization and transcription with `terminal(background=true, notify_on_complete=true)` + `process(action="wait")` — NEVER inline/foreground.** For carousel posts: extract all slides. For Threads: try web_extract or browser. **Language: content in source language, labels in English.** Save to Knowledge base/. Push after each note. 2 transcriptions max per worker.
```

## Assignee selection

| Content type | Assignee | Why |
|---|---|---|
| Image posts, text threads, carousels | `researcher` | No transcription — metadata extraction, web_extract, or browser |
| Video (Instagram Reels, YouTube, Threads) | `researcher-videos` | Requires download → diarization → transcription pipeline. `max_spawn=1` for RAM. |

## Key elements

| Element | Purpose |
|---------|---------|
| `Rate-limit strictly: sleep 8-15s` | Avoids Instagram rate-limiting / shadow-ban |
| `max 2MB/s` | Throttle yt-dlp download speed |
| `cookies at /root/.hermes/cookies/ig_cookies.txt` | Required for Instagram authentication |
| `Diarization MANDATORY for ALL video` | Never skip — use scripts/diarize.py + scripts/transcribe.py. Even monologues can have guest intros or Q&A segments |
| `HARD CAP 2 slides` | Carousel anti-bot limitation — slides 3+ are blocked |
| `Keep original language` | Content in source language, labels in English |
| `Knowledge base/` | Target folder in Obsidian vault |
| `Push after each note` | Git push so Obsidian syncs |
| `--parent <id>` | Chain tickets so they process sequentially |
| `--max-runtime 3600` | 1h safety net per ticket |

## Books (ePub/PDF)

```bash
hermes kanban --board knowledge-base create \
  --assignee researcher \
  --skill knowledge-base \
  --max-runtime 3600 \
  --body "..." \
  "KB: <Book Title> — <Author> (YYYY)"
```

**Never chain books** — each book gets its own independent ticket, no `--parent`.

**Exception: scanned PDFs requiring OCR.** Chain the OCR ticket with `--parent` to the last non-OCR ticket so `marker_single` runs solo (no concurrent workers = no OOM risk). For scanned PDFs >100 pages, OCR inline with `--page_range` chunks before ticketing (see book-extraction skill).

### Book ticket body template

```
Book: Title — Author (YYYY)

Source file: /tmp/books_extracted/<filename>.epub
CRITICAL: Use unique temp paths — multiple workers run in parallel! Use /tmp/book_<slug>.epub and /tmp/book_<slug>_full.txt. NEVER /tmp/book.epub.

FOLLOW books-extraction.md pipeline EXACTLY:
1. Extract full text from ePub — preserve chapter order, no sorting by size
2. Read EVERY chapter in full — no sampling, no exceptions. Even short prefaces/intros.
3. Create structured note from book-note-template.md (English labels, quotes in original language)
   - Chapter Summaries: EVERY chapter gets a substantive paragraph — this must be the dominant section
   - ≥4 direct quotes with chapter numbers (> format)
4. ≥2 fact-checks via web_search per fact-check-workflow.md
5. Critical Analysis MUST be shorter than Chapter Summaries + Key Claims combined. Content first, critique second.
6. Upload source epub + full extracted txt to MinIO (books/<slug>)
7. source_file frontmatter must be set to MinIO URL
8. Git add + commit + push

Minimum quality bar BEFORE pushing: ≥4 quotes, ≥2 fact-checks, chapter summaries are the dominant section (not critical analysis), Who Is the Author section, ≥100 lines (excl. frontmatter). Budget 2-3 rounds. Never push v1.
```

## Pitfalls

### Threads tickets must explicitly say "use curl, not Firecrawl"

Workers default to `web_extract` / `browser` for web content. Threads posts need curl + cookies per `pipeline-threads.md`. Ticket bodies MUST include: **"Use ONLY curl + cookies per pipeline-threads.md. Do NOT use Firecrawl, web_extract, or browser."** If the ticket body is ambiguous about extraction method, the worker will try Firecrawl/browser first and fail.

## Books

Books follow a distinct pattern from URLs — one ticket per book, no chaining.

```bash
# One ticket per book — no --parent, no chaining
hermes kanban --board knowledge-base create \
  --assignee researcher \
  --skill knowledge-base \
  --max-runtime 3600 \
  --body "..." \
  "KB: <book-title> — <author>"
```

### Book ticket body template

```
Book: <title> — <author> (<year>)

The ePub source is at /tmp/books/<filename>.epub (or download from MinIO with mc cp).
CRITICAL: Use unique temp paths — multiple workers run in parallel. Use /tmp/book_<slug>.epub and /tmp/book_<slug>_full.txt. NEVER /tmp/book.epub.

Pipeline:
1. Extract ePub to /tmp/book_full.txt — preserve chapter order (references/books-extraction.md Step 2)
2. Read EVERY chapter in full — no sampling, no exceptions. Use read_file with offset/limit.
3. Create structured note from templates/book-note-template.md:
   - Chapter Summaries: EVERY chapter gets a substantive paragraph — this must be the dominant section
   - ≥4 direct quotes with chapter numbers (> format)
   - ≥2 fact-checks via web_search (references/fact-check-workflow.md)
   - Critical Analysis MUST be shorter than Chapter Summaries + Key Claims combined
   - Author background, nuances
   - Note ≥ 100 lines (excluding frontmatter)
   - Budget 2-3 rounds — never push v1
4. Upload source + full text to MinIO: minio/knowledge-base/books/<slug>.epub + .txt
5. Push to Git: git add -A && git commit -m "add: <slug> — <author>" && git push

Language: ALL English. Labels in English, quotes in original language.
```

### Book-specific rules

| Rule | Rationale |
|------|-----------|
| 1 ticket per book | Books are 50-150K words — one book fills a worker session |
| No `--parent` chaining | Each book is independent, no ordering dependency |
| Assignee: `researcher` | Text extraction, no video/transcription needed |
| `--skill knowledge-base` | Covers books-extraction.md, book-note-template.md, fact-check-workflow.md, minio-upload.md |

## Convention

- 5 URLs per ticket max
- Chain URL tickets with `--parent` so each batch waits for the previous one
- Books: 1 ticket per book, no `--parent`
- Skill: `knowledge-base`

## Parent/child delegation

When moving a URL (Reel, YouTube, Mega, etc.) to a child ticket:

1. **Create** the child ticket for that URL only
2. **Update the parent ticket body** — remove the delegated URL from the numbered list, or mark it `DELEGATED → child <child_id>`. The body drives execution; a comment alone is insufficient.
3. **Comment** on the parent: `"URL N delegated to child <child_id>"`
4. **handoff.md** — list each URL as `DONE`, `DELEGATED (child <id>)`, or `TO-DO`
5. **On resume** — read comments and handoff.md before processing the next URL

Duplicate transcription detection (`ps aux | grep transcribe`): `video-pipeline-global.md` (Pre-flight).

## Pitfall: "skip diarization for solo"

Do NOT write "skip diarization for solo" or "monologue — no diarization" in ticket bodies.
Diarization is mandatory for ALL video per `SKILL.md` working principles.
Even apparent monologues can have guest intros, Q&A segments, or off-camera remarks.
If a worker already wrote this in a ticket body or handoff, add a BODY UPDATE comment
correcting it to "Diarization MANDATORY — use canonical scripts/diarize.py".

## Recently completed batch titles ("titre des done")

When the user asks for titles of recently processed content from completed batches:

```bash
cd "$OBSIDIAN_VAULT_PATH" && git log --oneline -20
# Then for range: git diff --name-only HEAD~N..HEAD | sort
```

Present note slugs as a bullet list. Don't re-read every note — quick inventory only.
