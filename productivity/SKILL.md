---
name: knowledge-base
description: "Manage a personal knowledge base in the Obsidian vault: capture and structure info about sante, sciences, histoire, livres, faits divers, etc."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [knowledge-management, research, notes]
    related_skills: [obsidian]
---

# Knowledge Base

Personal knowledge base stored in the Obsidian vault under `Connaissances/`.
Uses the `obsidian` skill for all file operations (read, write, search).

## Categories

| Folder | What goes there |
|--------|----------------|
| `Connaissances/sante/` | Santé, nutrition, parasites, yeux, cheveux, peau, TDAH, sommeil |
| `Connaissances/sciences/` | Physique, biologie, chimie, astronomie, techno, maths |
| `Connaissances/histoire/` | Événements, périodes, personnages, civilisations |
| `Connaissances/astrologie/` | Astrologie, thèmes, planètes, maisons, signes |
| `Connaissances/livres/` | Résumés, citations, notes de lecture |
| `Connaissances/faits-divers/` | Anecdotes, faits insolites, curiosités |
| `Connaissances/videos/` | Vidéos YouTube : transcriptions, résumés, points clés |
| `Connaissances/divers/` | Tout le reste |

## Content sources

### Instagram Reels & Image Posts

For Reels: see `references/extracting-content.md` for the full pipeline — Googlebot metadata → yt-dlp + cookies (Method A) or CDN-direct (Method B) → faster-whisper transcription → note.

For image posts (`/p/` URLs): run `scripts/ig-carousel-extract.py URL`. Extracts first 2 slides with full alt text — no vision_analyze needed (alt text contains the complete slide text). ⚠️ Slides 3+ are blocked by Instagram anti-bot in all headless browser modes (old headless, new headless, touch events, mobile viewport, arrow keys, mouse clicks, network interception — all tested, all fail). Accept this limitation or use manual screenshots.

Vision tool pitfalls: see `references/vision-pitfalls.md` — dual-section config trap, session caching, model availability, direct Anthropic API fallback.

Cookie requirements: Instagram needs a valid `sessionid` cookie. `csrftoken` + `mid` alone are insufficient. Validate with `grep -c sessionid /tmp/ig_cookies.txt` — must be ≥1. Export via a Reel URL (not homepage) or the sessionid won't be included. Re-export from browser if missing.

### External Video Files (Mega.nz, direct URLs)

For video files hosted outside YouTube: `references/mega-video-pipeline.md` covers Mega.nz download (mega.py), the two-phase kanban ticket pattern (Phase A: download+transcribe, Phase B: summarize+note+archive), cleanup safety, and worker profile settings.

### YouTube Videos

See `references/youtube-extraction.md` for the full pipeline: yt-dlp download (WebM VP9+Opus, max 720p) → faster-whisper `small` transcription → chapitrage (YouTube native chapters, NLP fallback) → chapter summaries + key points → video + MP3 audio + transcript JSON archived in MinIO → note in `Connaissances/videos/`. Note template in `references/youtube-note-template.md`.

Design decisions (grill session 2026-05-23):
- faster-whisper ONLY (no youtube-transcript-api). Quality over speed.
- WebM VP9+Opus 720p (space-efficient). MP3 audio extracted separately.
- Notes in `Connaissances/videos/` (dedicated folder).
- Summary + key points per chapter. No systematic fact-check (unlike books).
- Separate researcher profile `researcher-videos` with `max_spawn=1`.
- Max 2 videos per worker session. Rate-limit: 4 MB/s, sleep 1-10s.
- Cookies: `/tmp/yt_cookies.txt` (same approach as Instagram).
- **`--js-runtimes node` mandatory on all yt-dlp calls** — n-sig challenge blocks datacenter IPs even with cookies.

### Books (ePub/PDF)

See `references/book-extraction.md` for the full pipeline: ebooklib (ePub) or pymupdf/marker-pdf (PDF) → text extraction → chapter-by-chapter reading → claim extraction → structured note.

Books are 50-150K words — do NOT attempt to read the entire text in context. Read chapter by chapter, extract key claims, and synthesize.

## When to add a note

The user shares content (Instagram reel, article, study, book excerpt, tweet, conversation). You extract, verify if possible, and save.

If `web_extract` is unavailable (Firecrawl credits exhausted), use the techniques in `references/extracting-content.md` to extract metadata from Instagram and other platforms via `curl` with search-engine user-agents.

For free web search backends (DuckDuckGo, Brave, SearXNG), see `references/web-providers.md`.

## Adding a note — workflow

1. **Load the obsidian skill** (`skill_view(name='obsidian')`) for file ops
2. **Extract** the core claim, fact, or insight from the user's content
3. **Keep the original language** — do NOT translate. If the source is in English, the note is in English. If in French, French. The template section labels (Résumé, Contexte, etc.) may stay in French as they're structural, but content stays in source language.
4. **Verify** if possible — search for sources, cross-reference known facts
5. **Categorize** under the right subfolder from the table above
6. **Create** the note with `write_file()` using the vault path from `OBSIDIAN_VAULT_PATH`
7. **Upload source file** to MinIO if applicable (ePub, PDF) — see `references/minio-upload.md`
8. **Push to Git** so the user's Obsidian syncs: `cd "$OBSIDIAN_VAULT_PATH" && git add -A && git commit -m "add: <slug>" && git push`
9. **Confirm** to the user what was saved and where

For automated processing via kanban workers, the researcher profile setup is documented
in `references/researcher-profile-setup.md`.

### Extracting from Instagram / web when Firecrawl is down

If `web_extract` fails (Firecrawl credits exhausted), use `curl` directly:
- **Instagram Reels**: Use Googlebot UA to extract SEO metadata (og:title, og:description, likes/comments). See `references/instagram-extraction.md`.
- **Instagram Reels — video transcript**: Use yt-dlp + faster-whisper pipeline to extract full transcript from the video itself. See `references/extracting-content.md` (section "Video extraction + transcription").
- **GitHub raw**: `curl -sL https://raw.githubusercontent.com/...` for markdown/docs.
- **General pages**: `curl -sL URL` with grep for metadata.

## Books & long-form documents (PDF, ePub)

Books and long-form documents require a different workflow than short-form content (Reels, articles).
The full text is extracted, then summarized chapter by chapter rather than saved verbatim.

### Pipeline

1. Receive the file (scp, Telegram attachment, URL)
2. **Extract text**:
   - **PDF (text-based):** `pymupdf` — `python3 -c "import pymupdf; doc=pymupdf.open('file.pdf'); [print(p.get_text()) for p in doc]"`
   - **PDF (scanned/OCR):** `marker-pdf` — `marker_single file.pdf --output_dir /tmp/out`
   - **ePub:** `ebooklib` — see `references/books-pipeline.md` for the full extraction script
   - **Remote PDF:** `web_extract(urls=[...])` first, fall back to local extraction
3. **Summarize** — key claims, chapter-by-chapter digest, notable quotes
4. **Fact-check** the most significant claims (see `references/fact-check-workflow.md`)
5. **Save** structured note in `Connaissances/livres/` with:
   - Full bibliographic metadata (author, title, year, ISBN if available)
   - Chapter summaries with key claims
   - Fact-checked claims with confidence levels
   - Notable quotes with page/chapter references
   - Optionally: full extracted text as a reference file

### Language rule

**Never translate content.** Note body language matches source language.
Template section labels (Résumé, Contexte, etc.) stay in French as structural elements.

See `references/books-pipeline.md` for the complete extraction scripts and anti-pitfalls.

## Template

```markdown
---
topic: [topic1, topic2]
date: YYYY-MM-DD
source: <platform/author, date>
source_url: <optional URL>
source_file: <optional permanent URL — MinIO, not /tmp/>
confidence: verified | plausible | emerging | debunked | untested
tags: [tag1, tag2, tag3]
---

# Title

## Résumé
2-3 phrases. L'essentiel en haut.

## L'affirmation / Le fait
Ce qui est affirmé. Citation si pertinent.

## Contexte / Analyse
Développement, preuves, contre-arguments.

## Nuances
Ce que la source omet, exagère, ou déforme. Limitations.

## Fiabilité
✅ verified — confirmé par sources solides
⚠️ plausible — logique, quelques sources
🔬 emerging — recherche/préliminaire
❌ debunked — contredit par les preuves
❓ untested — pas de sources trouvées

## Sources
- Source originale
- Sources consultées

## Voir aussi
- [[Note liée 1]]
- [[Note liée 2]]
```

## Confidence levels

| Level | Meaning |
|-------|---------|
| ✅ verified | Confirmé par plusieurs sources solides |
| ⚠️ plausible | Logique, quelques sources, pas de consensus |
| 🔬 emerging | Préliminaire, prometteur mais limité |
| ❌ debunked | Contredit par les preuves disponibles |
| ❓ untested | Aucune source trouvée |

## Retrieving information

When the user asks "qu'est-ce qu'on a sur X ?":
1. Load the obsidian skill
2. `search_files(target='content', pattern='<keyword>', path='<vault>/Connaissances/')`
3. Present findings grouped by confidence level
4. If not found, offer to research and add

## Notes

- The vault path is in `OBSIDIAN_VAULT_PATH` (from `~/.hermes/.env`)
- For syncing the vault between server and desktop, load the `obsidian` skill and see its `references/git-sync.md`
- Wikilinks connect notes across categories — Obsidian handles these natively
- Slugs should be descriptive: `champignons-soleil-vitamine-d.md`, not `note1.md`
- Always include `source` and `source_url` — provenance matters
- **Ne pas référencer `/tmp/` dans une note** — uploader sur MinIO et utiliser `source_file`. Voir `references/minio-storage.md`.
- When Firecrawl/DDG can't extract Instagram reels, use `curl` + Googlebot UA — see `references/instagram-extraction.md`. For full video transcript, use the yt-dlp + cookies pipeline — see `references/extracting-content.md` (Method A).
- For extracting content from Instagram Reels without browser/Firecrawl, see `references/extracting-content.md`
- After creating or updating a note, push to Git so the user's Obsidian syncs: `cd "$OBSIDIAN_VAULT_PATH" && git add -A && git commit -m "add: <slug>" && git push`
- For books (PDF/ePub), see `references/books-pipeline.md` — includes extraction scripts, summarization strategy, and book-specific note template
- For YouTube video extraction (download, transcribe, chapter, archive to MinIO), see `references/youtube-extraction.md` and the note template at `references/youtube-note-template.md`
- For the video summarization prompt used by `researcher-videos` workers, see `references/resume-prompt.md`
- For external video files (Mega.nz, direct URLs), see `references/mega-video-pipeline.md` — two-phase kanban pattern with context-isolated LLM summarization
- For Instagram image carousel extraction, run `scripts/ig-carousel-extract.py URL`
- For free web search backends (DuckDuckGo, Brave, SearXNG), see `references/web-providers.md`
- For researcher profile setup (kanban worker), see `references/researcher-profile-setup.md`
