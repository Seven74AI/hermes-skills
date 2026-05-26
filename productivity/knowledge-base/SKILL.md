---
name: knowledge-base
description: "Manage a personal knowledge base in the Obsidian vault: capture and structure info about sante, sciences, histoire, livres, faits divers, etc."
version: 1.2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [knowledge-management, research, notes]
    related_skills: [obsidian]
---

# Knowledge Base

Personal knowledge base stored in the Obsidian vault under `Knowledge base/`.
All notes are in a flat directory — categorization is done via tags in the frontmatter,
not subfolders.

Uses the `obsidian` skill for all file operations (read, write, search).

## Note format

Save notes as `Knowledge base/<slug>.md`. No subfolders — use tags for categorization.

Save to `Knowledge base/`. Push after each note.

## Content sources

### YouTube Videos — two paths

**Quick transcript** (captions, no download): use the `youtube-content` skill — youtube-transcript-api, fast, one-off summaries.

**Full pipeline** (diarization + whisper + Obsidian note): use this skill (`knowledge-base`) — download → diarize → transcribe → archive. For durable knowledge capture, not quick lookups.

### Instagram Reels & Image Posts

**⚠️ URL type verification:** `/p/` = image carousel, `/reel/` = video. Pipelines are completely different. Users sometimes say "reel" while pasting a `/p/` URL. **Always confirm the URL type** before running any pipeline.

For Reels: see `references/pipeline-instagram.md` for the full pipeline — Googlebot metadata → yt-dlp + cookies (Method A) → dual audio extraction (16kHz + 8kHz WAV) → pyannote diarization + faster-whisper `large-v3` transcription (same as YouTube pipeline) → note.

For image posts (`/p/` URLs): run `scripts/ig-carousel-extract.py URL`. Extracts first 2 slides with full alt text — no vision_analyze needed (alt text contains the complete slide text). ⚠️ Slides 3+ are blocked by Instagram anti-bot in all headless browser modes (old headless, new headless, touch events, mobile viewport, arrow keys, mouse clicks, network interception — all tested, all fail). Accept this limitation or use manual screenshots.

Vision tool pitfalls: see `references/vision-pitfalls.md` — dual-section config trap, session caching, model availability, direct Anthropic API fallback.

Cookie requirements: Instagram needs a valid `sessionid` cookie. `csrftoken` + `mid` alone are insufficient. Validate with `grep -c sessionid /tmp/ig_cookies.txt` — must be ≥1. Export via a Reel URL (not homepage) or the sessionid won't be included. Re-export from browser if missing.

### External Video Files (Mega.nz, direct URLs)

For video files hosted outside YouTube: `references/pipeline-mega.md` covers Mega.nz download (mega.py), the two-phase kanban ticket pattern (Phase A: download+transcribe, Phase B: summarize+note+archive), cleanup safety, and worker profile settings.

### YouTube Videos

Same two-phase kanban pattern as Mega (see above). Both pipelines use `references/resume-prompt.md`
for the Phase B summarization — a two-pass LLM prompt producing 7-section deep notes
(Résumé → Métadonnées → Concepts clés → Chapitres → Points clés → Nuances & Limites →
Extractions utiles).

Phase A (mécanique): `references/pipeline-youtube.md` — yt-dlp download (WebM VP9+Opus,
max 720p) → dual audio extraction (16kHz WAV + 8kHz WAV) → pyannote diarization (8kHz) + faster-whisper
`large-v3` transcription (16kHz) → speaker identification → chapitrage (YouTube native chapters, NLP fallback).
**Toujours `background=true, notify_on_complete=true` + `process(wait)` pour pyannote et whisper — jamais de heartbeats.**
Phase B (LLM): `references/resume-prompt.md` → note in `Knowledge base/` via
`references/youtube-note-template.md` → MinIO → git push.

Design decisions (grill session 2026-05-23, updated 2026-05-24):
- faster-whisper ONLY (no youtube-transcript-api). Quality over speed.
- **Speaker diarization on ALL multi-speaker videos** — YouTube AND Instagram Reels — via manual pyannote + faster-whisper pipeline
  (not whisperx — manual for full control over each stage). 8kHz WAV audio for pyannote
  (RAM-efficient, ⚠️ WAV obligatoire — MP3 rejeté), 16kHz for whisper. Continuous speaker labels across full duration,
  no chunking. HF token for initial model download only — fully local after.
  
  **⚠️ Skip diarization for single-speaker content** (monologues, solo Reels, direct-to-camera talks).
  Diarization on a 13-min CPU-only monologue costs ~40 min for zero value. Use faster-whisper directly
  with `speaker: 'SPEAKER_00'` for all segments. Mention in the note that the video is single-speaker.
- **Whisper model:** `large-v3` mandatory for all video pipelines (noms propres, idiomes, syntaxe).
  `medium` / `small` not used — quality over speed. ~2-3× realtime transcription + ~2-3× diarization (pyannote >=4.0 required with torch >=2.5 — 3.x API incompatible).
  See `references/whisper-model-comparison.md` for benchmarks.
- **pyannote version:** `>=4.0` mandatory when torch >=2.5. torch 2.5+ removed `AudioMetaData` and `list_audio_backends` which pyannote 3.x requires. Pin: `pip install 'pyannote.audio>=4.0'`. API change in 4.x: iterate `for segment in diarization` directly (no `.itertracks()`).
- **Dependency cascade:** `marker-pdf` silently downgrades `openai`/`anthropic`/`tenacity`/`Pillow`/`huggingface-hub` — breaking hermes-agent. After installing marker-pdf, always restore hermes-agent's required versions (see `references/pipeline-instagram.md` prerequisites).
  See `references/whisper-model-comparison.md` for benchmarks.
- **Overlap handling:** composite labels (`SPEAKER_00 | SPEAKER_01`) kept in transcript
  with `⚠️ Chevauchement` annotation in notes. Transcription is less reliable on overlaps.
- **Speaker identification:** heuristic from video metadata (description, title, channel).
  Unmatched speakers remain "Unknown". Prefer Unknown over incorrect identification.
- **Per-speaker summary** in addition to per-chapter summary. Who covered what topics,
  time spoken, main thesis.
- **Hard fail on diarization failure:** if pyannote crashes/OOMs/times out, the ticket
  fails entirely. No silent fallback to transcription-only — the error must be visible.
- **No re-processing of existing videos:** videos already transcribed without diarization
  stay as-is. Only new videos use the full pipeline.
- **No parallelization:** `max_spawn=1` for researcher-videos profile. Videos are processed
  sequentially to keep RAM predictable (~3-4 GB max for 9h video).
- WebM VP9+Opus 720p (space-efficient). MP3 audio extracted separately.
- Notes in `Knowledge base/` (dedicated folder).
- Summary + key points per chapter. No systematic fact-check (unlike books).
- Separate researcher profile `researcher-videos` with `max_spawn=1`.
- Max 2 videos per worker session. Rate-limit: 4 MB/s, sleep 1-10s.
- Cookies: `/tmp/yt_cookies.txt` (same approach as Instagram).
- **`--js-runtimes node` mandatory on all yt-dlp calls** — n-sig challenge blocks datacenter IPs even with cookies.

### Books (ePub/PDF)

See `references/book-extraction.md` for the full pipeline: ebooklib (ePub) or pymupdf/marker-pdf (PDF) → text extraction → chapter-by-chapter reading → claim extraction → structured note.

Books are 50-150K words — do NOT attempt to read the entire text in context. Read chapter by chapter, extract key claims, and synthesize.

## Creating kanban tickets for batch processing

When the user drops a list of URLs to process, create tickets on the `default` board.
See `references/kanban-ticket-template.md` for the full template.

Quick reference:
- 5 URLs max per ticket
- Chain with `--parent` for sequential processing
- `--assignee researcher --skill knowledge-base --max-runtime 3600`
- Body must include: rate-limit instructions, cookie path, language rule, save path

## When to add a note

The user shares content (Instagram reel, article, study, book excerpt, tweet, conversation). You extract, verify if possible, and save.

If `web_extract` is unavailable (Firecrawl credits exhausted), use the techniques in `references/pipeline-instagram.md` to extract metadata from Instagram and other platforms via `curl` with search-engine user-agents.

For free web search backends (DuckDuckGo, Brave, SearXNG), see `references/web-providers.md`.

## Adding a note — workflow

1. **Load the obsidian skill** (`skill_view(name='obsidian')`) for file ops
2. **Extract** the core claim, fact, or insight from the user's content
3. **Content = source language. Labels = always in English.** If the source is French, the content is in French but section labels are "Summary", "Key Concepts", etc. If English, everything is English. Never translate content.
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
- **Instagram Reels — video transcript**: Use yt-dlp + faster-whisper pipeline to extract full transcript from the video itself. See `references/pipeline-instagram.md` (section "Video extraction + transcription").
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
5. **Save** structured note in `Knowledge base/` with:
   - Full bibliographic metadata (author, title, year, ISBN if available)
   - Chapter summaries with key claims
   - Fact-checked claims with confidence levels
   - Notable quotes with page/chapter references
   - Optionally: full extracted text as a reference file

### Language rule

**Content = source language. Labels = always English.** Never translate content.
English source → English content. French source → French content.
Section labels (Summary, Key Concepts, Chapters...) are always in English regardless.

See `references/books-pipeline.md` for the complete extraction scripts and anti-pitfalls.

## Template

Labels are always in English. Content follows source language.

```markdown
---
topic: [topic1, topic2]
date: YYYY-MM-DD
source: <platform/author, date>
source_url: <optional URL>
confidence: verified | plausible | emerging | debunked | untested
tags: [tag1, tag2, tag3]
---

# Title

## Summary
2-3 sentences. The essential up top.

## The Claim
What is claimed. Quote if relevant.

## Context / Analysis
Development, evidence, counter-arguments.

## Nuances
What the source omits, exaggerates, or distorts. Limitations.

## Reliability
✅ verified | ⚠️ plausible | 🔬 emerging | ❌ debunked | ❓ untested

## Sources
- Original source
- Consulted sources

## See Also
- [[Related note 1]]
- [[Related note 2]]
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
2. `search_files(target='content', pattern='<keyword>', path='<vault>/Knowledge base/')`
3. Present findings grouped by confidence level
4. If not found, offer to research and add

## User Preferences

- **No compromises.** Don't skip steps in the pipeline for convenience. If the skill says diarization is required for multi-speaker content, do it. If it says large-v3 is mandatory, use it. The user will wait.
- **Skill updates over memory updates.** When knowledge is discovered (fixes, pitfalls, API changes, new commands), update the skill first, not just memory. Memory captures state; skills capture how-to.
- **Visibility.** The user blocks commands they haven't approved (curl pipes, mass installs). Show what you're about to do before doing it for non-trivial operations.

## Pitfalls

### /p/ vs /reel/ URL — always verify before running pipeline

Instagram `/p/` URLs are image carousels; `/reel/` URLs are videos. The pipelines are completely different. Users sometimes say "reel" while pasting a `/p/` URL. **Always confirm the URL type** before running. Running the wrong pipeline wastes time and produces unusable output. If ambiguous, ask: "C'est bien un Reel vidéo ou un post image ?"

### marker-pdf cascade downgrades critical hermes-agent dependencies

Installing `marker-pdf` pulls in older versions of `openai`, `anthropic`, `tenacity`, `tokenizers`, `huggingface-hub`, and `Pillow` that break hermes-agent. After installing the book-extraction packages, re-pin the originals:

```bash
pip install 'openai==2.24.0' 'anthropic==0.87.0' 'tenacity==9.1.4' 'Pillow==12.2.0' 'huggingface-hub==1.16.1' 'tokenizers==0.23.1'
```

Check for conflicts with `pip check` afterward. The only expected warning is `mega-py` wanting `tenacity<6` — this is cosmetic, mega.py works fine with tenacity 9.x.

### Language drift: French prompts bias LLM toward French output

Even with explicit "do not translate" rules, a 100% French prompt (`resume-prompt.md`)
biases the LLM toward producing French output. Observed 2026-05-24: English Instagram
reel transcribed correctly, but the resulting Obsidian note was entirely in French
(labels AND content).

**Fix**: strengthened language rules in all prompts — "NE TRADUIS JAMAIS" + "labels = always
English" directives at the TOP of prompts, not buried in footers. Added REGLE LANGUE
banner at the top of `youtube-note-template.md`.

## Notes

- The vault path is in `OBSIDIAN_VAULT_PATH` (from `~/.hermes/.env`)
- For syncing the vault between server and desktop, load the `obsidian` skill and see its `references/git-sync.md`
- Wikilinks connect notes across categories — Obsidian handles these natively
- Slugs should be descriptive: `champignons-soleil-vitamine-d.md`, not `note1.md`
- Always include `source` and `source_url` — provenance matters
- **Ne pas référencer `/tmp/` dans une note** — uploader sur MinIO et utiliser `source_file`. Voir `references/minio-storage.md`.
- When Firecrawl/DDG can't extract Instagram reels, use `curl` + Googlebot UA — see `references/instagram-extraction.md`. For full video transcript, use the yt-dlp + cookies pipeline — see `references/pipeline-instagram.md` (Method A).
- For extracting content from Instagram Reels without browser/Firecrawl, see `references/pipeline-instagram.md`
- After creating or updating a note, push to Git so the user's Obsidian syncs: `cd "$OBSIDIAN_VAULT_PATH" && git add -A && git commit -m "add: <slug>" && git push`
- For books (PDF/ePub), see `references/books-pipeline.md` — includes extraction scripts, summarization strategy, and book-specific note template
- For YouTube video extraction (download, transcribe, chapter, archive to MinIO), see `references/pipeline-youtube.md` and the note template at `references/youtube-note-template.md`
- For the video summarization prompt used by `researcher-videos` workers in BOTH YouTube and Mega Phase B, see `references/resume-prompt.md` — two-pass LLM, 7-section deep notes
- For external video files (Mega.nz, direct URLs), see `references/pipeline-mega.md` — two-phase kanban pattern with context-isolated LLM summarization
- For Instagram image carousel extraction, run `scripts/ig-carousel-extract.py URL`
- For the full dependency checklist (pip packages, system deps, models, post-install fixes): `references/dependencies.md`
- For free web search backends (DuckDuckGo, Brave, SearXNG), see `references/web-providers.md`
- For researcher profile setup (kanban worker), see `references/researcher-profile-setup.md`
- **After VPS migration or fresh install:** run `references/fresh-install-checklist.md` to verify all pipeline deps, services, and configs survived the move
- **Skill sync to GitHub:** custom skills go to `Seven74AI/hermes-skills` via `/root/.hermes/scripts/sync-skills-to-github.py` (cron `4eee7fb0b484`, daily 3:30 AM). To add a new custom category: edit `CUSTOM_CATEGORIES` set + add bundled exclusions to `BUNDLED_SKILLS`.
