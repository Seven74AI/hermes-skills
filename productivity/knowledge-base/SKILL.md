---
name: knowledge-base
description: "Manage a personal knowledge base in the Obsidian vault: capture and structure information"
version: 1.10.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [knowledge-management, research, notes]
    related_skills: [obsidian]
---

# Knowledge Base

Personal knowledge base in the Obsidian vault at `Knowledge base/`.
Categorize with Obsidian `tags` in frontmatter.
Uses the `obsidian` skill for file operations. Git push after each note.

## Content sources

### YouTube

Pipeline: download → diarize → transcribe → summarize → archive with faster-whisper `large-v3`.

- Phase A: `references/pipeline-youtube.md`
- Phase B: `references/resume-prompt.md` + `references/youtube-note-template.md`
- Kanban pattern: same two-phase flow as Mega (`references/pipeline-mega.md`)

### Threads

`references/pipeline-threads.md` — detect text vs video via `video_versions` in JSON (NOT `og:type`), session cookies required, content gate (skip login-wall and og-only posts). 7 known pitfalls documented in the pipeline reference.

- Cookies: `/root/.hermes/cookies/threads_cookies.txt` (export from Chrome Profile 5)
- `video_versions` present → `researcher-videos` (video, diarize). No `video_versions` → `researcher` (text).
- **Never create a note from `og:description` alone** — it's a preview, not the post. Skip inaccessible posts.
- yt-dlp does NOT support Threads. Use curl + cookies for extraction.
- Note prefix: `threads-`
- **Phase 0 — Pre-ticket detection** (`references/pipeline-threads.md`): run content-type detection BEFORE creating kanban ticket. `video_versions` present → `--assignee researcher-videos`. Absent → `--assignee researcher`.
- `media_type=19` is an Instagram video cross-post (NOT a carousel). Always check for `video_versions` regardless of outer type. See `references/threads-media-types.md`.
- Dedup: check vault for existing `source_url` before creating a note

### Substack

`references/pipeline-substack.md` — extraction Firecrawl, nettoyage markdown, note Obsidian. Pas besoin de cookies pour les articles publics.

- Dedup: check vault for existing `source_url` **before creating kanban ticket** (Phase -2).

### Instagram

Route by URL path:

| Path | Pipeline |
|------|----------|
| `/reel/` | `references/pipeline-instagram.md` |
| `/p/` | `scripts/ig-carousel-extract.py` (first 2 slides; manual screenshots for slides 3+) |

When the user's description disagrees with the URL path, confirm the type first.

- Cookies: validate `sessionid` before Reel downloads (see `references/edge-cases.md`)
- Metadata: `references/instagram-extraction.md`
- Vision: `references/vision-pitfalls.md`

### Video (all platforms)

`references/video-pipeline-global.md` — background execution, mandatory diarization (pyannote), `large-v3` transcription, canonical scripts, rate limits, transcription persistence.

### Books (ePub/PDF)

`references/books-extraction.md` — extract text, read chapter by chapter, synthesize. Template: `templates/book-note-template.md`. Upload source to MinIO (see `references/minio-upload.md`).

### Web search

`references/web-providers.md`

## Kanban batch processing

When the user drops URLs, create tickets on the `default` board.
See `references/kanban-ticket-template.md`.

- 5 URLs per ticket; chain with `--parent`
- 2 video transcriptions per worker session (`video-pipeline-global.md`)
- `--max-runtime 3600`
- Assignee: `researcher` (text/image) or `researcher-videos` (video)
- Worker setup: `references/researcher-profile-setup.md`

## Cookie handling

All pipelines that require cookies (YouTube, Instagram, Threads) must run a pre-flight validation before processing. If validation fails, **skip the URL, do not block the ticket**:

```bash
echo "URL" >> /root/.hermes/queues/skipped_<platform>.txt
# + send Telegram notification
```

Queue files: `skipped_yt.txt`, `skipped_threads.txt`, `skipped_ig.txt`, `skipped_substack.txt` under `/root/.hermes/queues/`.

When the user refreshes cookies and says "relance": validate cookies → load `knowledge-base` skill → process queue file from the top. Full procedure: `references/edge-cases.md` (Cookie validation section).

## When to add a note

User shares content → extract, verify when possible, save.

If `web_extract` is unavailable: `curl` + Googlebot UA (`references/instagram-extraction.md`) or yt-dlp for Reel transcripts (`references/pipeline-instagram.md`).

## Adding a note — workflow

1. **Load obsidian skill** (`skill_view(name='obsidian')`)
2. **Extract** core claim, fact, or insight
3. **Language:** content in source language; section labels per template (English)
4. **Verify** when possible — search, cross-reference
5. **Tag** via frontmatter (`tags`)
6. **Create** `Knowledge base/<slug>.md` via `OBSIDIAN_VAULT_PATH`
7. **Upload** source to MinIO when applicable — `references/minio-upload.md`
   - **Verify each upload** immediately — `mc ls minio/<bucket>/<path>` for every file referenced in the note frontmatter. If a file is missing, re-upload before pushing.
8. **Push:** `cd "$OBSIDIAN_VAULT_PATH" && git add -A && git commit -m "add: <slug>" && git push`
9. **Confirm** what was saved — re-read the note, verify all `minio://` references resolve (`references/minio-integrity.md`), check diarization was applied (transcripts should have speaker labels, not just `?`)

Edge cases (cookies, music-only Reels, delegation): `references/edge-cases.md`

## Template

```markdown
---
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
- [[existing-note-slug]] — verified with `grep -rl "slug:" "$OBSIDIAN_VAULT_PATH/Knowledge base/"` before linking
- Only link to notes that actually exist. No invented wikilinks.
- If no existing note is relevant, omit this section entirely.
```

## Confidence levels

| Level | Meaning |
|-------|---------|
| ✅ verified | Confirmed by multiple solid sources |
| ⚠️ plausible | Logical, some sources, no consensus |
| 🔬 emerging | Preliminary, promising but limited |
| ❌ debunked | Contradicted by available evidence |
| ❓ untested | No source found |

## Retrieving information

When the user asks "qu'est-ce qu'on a sur X ?":
1. Load obsidian skill
2. `search_files(target='content', pattern='<keyword>', path='<vault>/Knowledge base/')`
3. Present findings grouped by confidence
4. Offer to research and add if nothing matches

Batch inventory ("titre des done"): `references/kanban-ticket-template.md`

## Working principles

- **Ticket bodies are neutral.** Just the facts: URL, source, date, content type, technical instructions. No editorializing, no judgment on the content, no confidence level pre-assigned. Let the worker determine confidence after processing.
- Complete every pipeline step — the user will wait for quality
- **Diarization is mandatory for ALL video content** (YouTube, Instagram Reels, Mega). Use canonical `scripts/diarize.py` + `scripts/transcribe.py`. Never skip diarization — even for apparent monologues (guest intros, Q&A segments, off-camera remarks are common in "solo" videos).
- Verify every upload and reference: check MinIO files exist (`references/minio-integrity.md`), confirm diarization was applied (speaker labels must not be `?`), then push.
- Document discoveries in skill files (skills over memory)
- Show non-trivial commands before running them
- **Pipeline debugging: diagnose first, then confirm, then fix.** When identifying pipeline problems, present the evidence and root cause to the user BEFORE applying fixes. The user will verify on their end and may correct the diagnosis. Do not rush to patch — wait for confirmation, then apply the fix.
- **Keep skill docs minimal.** Reference files delegate to the main skill or umbrella reference — don't duplicate pipeline steps across files. If a procedure is already covered by loading `knowledge-base`, just say so.
- **Happy path only.** Pipeline references must contain only the workflow: what to do, in what order, with what commands. No edge cases, failure modes, deprecated methods, known pitfalls, "✅ FIXED" markers, or bad-path pollution. Those belong in the operator's journal, not in worker-facing skill files.
- **Sync profiles after editing skill files.** Worker profiles (`researcher`, `researcher-videos`) have their own copies of the skill directory. After changing any reference, template, or script, run `scripts/sync-to-profiles.sh` or the worker will use stale versions.

## Reference index

| Topic | File |
|-------|------|
| Substack | `references/pipeline-substack.md` |
| Edge cases | `references/edge-cases.md` |
| Video global rules | `references/video-pipeline-global.md` |
| YouTube pipeline | `references/pipeline-youtube.md` |
| Threads pipeline | `references/pipeline-threads.md` |
| Threads media types | `references/threads-media-types.md` |
| Instagram pipeline | `references/pipeline-instagram.md` |
| Mega / external video | `references/pipeline-mega.md` |
| Video summarization | `references/resume-prompt.md` |
| YouTube note template | `references/youtube-note-template.md` |
| Books | `references/books-extraction.md` |
| Kanban tickets | `references/kanban-ticket-template.md` |
| Worker profiles | `references/researcher-profile-setup.md` |
| MinIO | `references/minio-storage.md`, `references/minio-upload.md`, `references/minio-integrity.md` |
| Dependencies / fresh install | `references/dependencies.md`, `references/fresh-install-checklist.md` |
| Fact-checking | `references/fact-check-workflow.md` |
| Web search | `references/web-providers.md` |

Vault path: `OBSIDIAN_VAULT_PATH` (from `~/.hermes/.env`). Git sync: obsidian skill `references/git-sync.md`.
Persist transcripts and source files to MinIO
